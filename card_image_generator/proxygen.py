import itertools
import sys
import edn_format
import re
import pathlib
import yaml

from PIL import Image, ImageDraw, ImageFont


def pyfy(obj):
    """Transform clojure-y objects into the Python analogues."""
    if type(obj) is edn_format.edn_lex.Keyword:
        return str(obj)[1:]
    elif type(obj) is edn_format.immutable_list.ImmutableList:
        return [pyfy(subobj) for subobj in obj]
    else:
        return obj


def parse_text(text):
    """Given card text from NRDB, strip formatting tags and replace
    icon symbols by the appropriate characters in the font"""
    SYMBOL_TABLE = {
        '': '',
        '<em>': '',
        '</em>': '',
        '<li>': '\n ' + chr(183),
        '[credit]': chr(127) + ' ',
        '[link]': chr(128) + ' ',
        '[subroutine]': chr(129) + ' ',
        '[recurring-credit]': chr(130) + ' ',
        '[trash]': chr(131),
        '[click]': chr(132),
        '[mu]': chr(137) + ' ',
        '[shaper]': chr(140) + ' ',
        '[criminal]': chr(141) + ' ',
        '[anarch]': chr(142) + ' ',
        '[haas-bioroid]': chr(143) + ' ',
        '[jinteki]': chr(144) + ' ',
        '[nbn]': chr(145) + ' ',
        '[weyland]': chr(146) + ' ',
    }
    text = re.sub('<errata>(.*?)</errata>', '', text)
    text = re.sub(
        '<strong>(.*?)</strong>',
        lambda m: ''.join([chr(ord(c)+531) for c in m.group(1)]), text
    )
    text = re.sub(
        '<trace>(.*?)</trace>',
        lambda m: ''.join([chr(ord(c)+531) for c in m.group(1)]) + ' –', text
    )

    for symbol, font_char in SYMBOL_TABLE.items():
        text = text.replace(symbol, font_char)
    return text


def break_and_resize(draw, font_size, font_path, width, height, text):
    """Given a string, a fontsize and an ImageDraw object, intelligently(!) insert
    linebreaks at spaces to keep text width where it should be.
    If too tall, shrink font and retry."""

    font = ImageFont.truetype(font_path, size=font_size)
    words = re.split(r'(\s+)', text)
    num_extra_linebreaks = text.count('\n')
    end_break_long = []  # list so that element i is True iff linebreak i is long
    lines = []
    while words:
        line = words.pop(0)

        while words and (draw.textsize(line + words[0], font=font)[0] < width):
            w = words.pop(0)
            if re.match('(\s)*\n+(\s)*', w):
                end_break_long.append(True)
                break
            line += w
        else:
            end_break_long.append(False)

        lines.append(line)

    _, line_height = draw.textsize('a')
    split_text = '\n'.join(lines)
    text_height = draw.textsize(split_text, font=font)[1]
    text_height += 0.5 * num_extra_linebreaks * line_height

    if text_height > height and font_size > 7:
        return break_and_resize(draw, font_size-1, font_path, width, height, text)
    else:
        return split_text, font_size, end_break_long


try:
    edn_path = sys.argv[1]
    output_path = sys.argv[2]
    background_img_path = sys.argv[3] if len(sys.argv) > 3 else None
except IndexError:
    print("Usage: python proxygen.py path_to_card_data_edn output_image_path <optional: background_image_path>")
    sys.exit(1)


# load card data

with open(edn_path) as f:
    d = edn_format.edn_parse.parse(f.read())
    card_dict = {pyfy(k): pyfy(v) for k, v in d.items()}
card_type = card_dict['type']

# fetch appropriate template
# TODO: hardcoding will break if script is symlinked, consider adding script to package instead
resource_dir = pathlib.Path(__file__).parent / 'assets'
template_path = resource_dir / f'{card_type}.yaml'

with open(template_path) as f:
    template_dict = yaml.load(f)
template_img_path = resource_dir / template_dict['template_image'][card_dict['faction']]


# load the template image and background
template = Image.open(template_img_path).convert('RGBA')
outimg = Image.new(mode='RGBA', size=(template.width, template.height))

if background_img_path:
    bg = Image.open(background_img_path).convert('RGBA')
    bg = bg.resize((template.width, template.height))
    outimg.paste(bg)

outimg.paste(template, mask=template)

# TODO: Correct templates to use higher def images
outimg = outimg.resize((312, 444))

draw = ImageDraw.Draw(outimg)

# add inf dots
if card_dict.get('influence-cost'):
    inf_pip_path = resource_dir / template_dict['atoms']['influence-pip']
    infimg = Image.open(inf_pip_path).convert('RGBA')
    p0, p1 = [template_dict[f'influence-{i}']['loc'] for i in (1, 2)]
    for i in range(card_dict['influence-cost']):
        p = tuple(p0[j] + i*(p1[j] - p0[j]) for j in range(2))
        # now center
        p = (int(p[0] - infimg.width/2), int(p[1] - infimg.height/2))
        outimg.paste(infimg, p, mask=infimg)

# add trashcan icon to trashable operations/ice
if card_type in {'operation', 'ice'} and card_dict.get('trash-cost') is not None:
    trashcan_path = resource_dir / template_dict['atoms']['trashcan']
    trashcan = Image.open(trashcan_path).convert('RGBA')
    outimg.paste(trashcan, template_dict['trashcan']['loc'], mask=trashcan)

# now write everything else on there
for item in [
        'title',
        'subtitle',
        'text',
        'subtype',
        'cost',
        'advancement-requirement',
        'agenda-points',
        'memory-cost',
        'trash-cost',
        'strength',
        'base-link',
        'minimum-deck-size',
        'influence-limit',
        'type'
]:
    if item == 'subtype':
        subtype_replacements = {
            'ap': 'AP',
            'g-mod': 'G-mod',
            'ai': 'AI'
        }
        text = ' - '.join(
            [subtype_replacements.get(st.lower(), st.replace('-', ' ').title())
             for st in card_dict.get('subtype', [])]
        )
    elif item == 'type':
        if card_type == 'identity':
            continue
        text = card_type.upper() + ':'  # TODO: only have : if a subtype
    elif card_type == 'identity' and item in {'title', 'subtitle'}:
        text = card_dict['title'].split(': ')[0 if item == 'title' else 1]
    else:
        text = card_dict.get(item)
        if item == 'title' and card_dict.get('uniqueness'):
            text = chr(128) + text

    if text is None:
        if (item in {'cost', 'strength'}
            and card_type not in {'agenda', 'identity'}
            and item in card_dict):
            text = 'X'
        else:
            continue

    text = str(text)
    pos = template_dict[item]['loc']
    if type(pos) is dict:
        pos = pos[card_dict['faction']]
    pos = tuple(pos)
    font_path = str(resource_dir / template_dict[item]['font'])
    font_size = template_dict[item]['fontsize']
    font_color = tuple(template_dict[item].get('fontcolor', (0, 0, 0)))
    font = ImageFont.truetype(font_path, size=font_size)

    if item == 'text':
        # need to parse text and maybe change fontsize
        # also treat in-text linebreaks as indicating longer breaks
        textwidth, textheight = [template_dict['text'][s] for s in ['width', 'height']]
        text, font_size, end_break_long = break_and_resize(
            draw, font_size, font_path, textwidth,
            textheight, parse_text(card_dict['text'])
        )
        font = ImageFont.truetype(font_path, size=font_size)

        lineheight = draw.textsize('a', font=font)[1]
        linespacing = draw.textsize('a\na', font=font)[1] - 2*lineheight
        x, y = pos
        lines = text.split('\n')
        assert len(end_break_long) == len(lines)
        for is_special, line in zip(end_break_long, lines):
            line = line.strip()
            draw.text((x, y), line, font=font, fill=font_color)
            y += lineheight + (2 if is_special else 1) * linespacing
        continue

    if template_dict[item].get('center'):
        # TODO: center in height here as well
        tw, _ = draw.textsize(str(text), font)
        pos = (pos[0] - tw/2, pos[1])

    if template_dict[item].get('rotation') is None:
        if template_dict[item].get('backdrop'):
            bd_color = tuple(template_dict[item]['backdrop']['color'])
            width = template_dict[item]['backdrop']['width']
            ox, oy = template_dict[item]['backdrop']['offset']
            for dx, dy in [(-width, -width), (width, -width),
                           (-width, width), (width, width)]:
                draw.text((pos[0]+dx+ox, pos[1]+dy+oy), str(text),
                          font=font, fill=bd_color)

        draw.text(pos, str(text), font=font, fill=font_color)

    else:
        # need to draw text at an angle
        assert not template_dict[item].get('backdrop'), "Backdrop and rotation not supported"
        if item == 'subtype':
            text = 'ICE:  ' + text
        text_width, text_height = draw.textsize(str(text), font=font)
        tmpimg = Image.new('RGBA', tuple([max(text_width, text_height)]*2),
                           color=(0, 0, 0, 0))
        ImageDraw.Draw(tmpimg).text((0, 0), str(text),
                                    font=font, fill=font_color)
        tmpimg = tmpimg.rotate(template_dict[item].get('rotation'))
        outimg.paste(tmpimg, pos, mask=tmpimg)

outimg.save(output_path)
