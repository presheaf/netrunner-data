import edn_format
import re

from PIL import Image, ImageDraw, ImageFont


def pyfy(obj):
    if type(obj) is edn_format.edn_lex.Keyword:
        return str(obj)[1:]
    elif type(obj) is edn_format.immutable_list.ImmutableList:
        return [pyfy(subobj) for subobj in obj]
    # TODO: None too
    else:
        return obj


def make_template_path(card_type, faction):
    if faction == 'haas-bioroid':
        faction_str = 'haas'
    elif faction == 'weyland-consortium':
        faction_str = 'weyland'
    elif faction == 'neutral-runner' or faction == 'neutral-corp':
        faction_str = 'neutral'
    else:
        faction_str = faction
    return f'templates/{card_type}/{card_type}_{faction_str}.png'


def get_text_anchors(card_type, faction):
    # TODO: should also add inf dot locations
    if card_type == 'event':
        # taken from shaper
        return {'title': (68, 18),
                'subtype': (83, 280),
                'cost': (27, 32),
                'text': (36, 305),
                'textwidth': 245,
                'textheight': 100}
    elif card_type == 'hardware':
        # anarch
        return {'title': (64, 229),
                'subtype': (126, 266),
                'cost': (29, 34),
                'text': (48, 291),
                'textwidth': 240,
                'textheight': 106}
    elif card_type == 'resource':
        # criminal
        return {'title': (75, 17),
                'subtype': (100, 219),
                'cost': (28, 32),
                'text': (22, 246),
                'textwidth': 231,
                'textheight': 144}
    elif card_type == 'program':
        # anarch
        return {'title': (18, 208),
                'subtype': (100, 241),
                'cost': (26, 30),
                'memory-cost': (79, 19),
                'strength': (20, 405),
                'text': (36, 266),
                'textwidth': 243,
                'textheight': 124}
    elif card_type == 'identity':
        if faction in ['criminal', 'anarch', 'shaper', 'neutral-runner', 'apex', 'adam', 'sunny']:
            # crim
            return {'title': (104, 18),
                    'subtitle': (145, 41),
                    'subtype': (115, 333),
                    'base-link': (20, 22),
                    'minimum-deck-size': (268, 390),
                    'influence-limit': (268, 413),
                    'text': (45, 352),
                    'textwidth': 200,
                    'textheight': 80}
        else:
            # hb
            return {'title': (59, 28),
                    'subtitle': (28, 55),
                    'subtype': (106, 331),
                    'minimum-deck-size': (20, 388),
                    'influence-limit': (20, 413),
                    'text': (58, 358),
                    'textwidth': 237,
                    'textheight': 75}
    elif card_type == 'agenda':
        # hb
        return {'title': (27, 28),
                'subtype': (94, 286),
                'advancement-requirement': (271, 18),
                'agenda-points': (26, 226),
                'text': (36, 307),
                'textwidth': 242,
                'textheight': 90}
    elif card_type == 'asset':
        # hb
        return {'title': (34, 227),
                'subtype': (89, 258),
                'cost': (29, 29),
                'text': (35, 285),
                'trash-cost': (273, 372),
                'textwidth': 225,
                'textheight': 104}
    elif card_type == 'upgrade':
        # hb
        return {'title': (37, 232),
                'subtype': (110, 262),
                'cost': (29, 35),
                'text': (45, 289),
                'trash-cost': (276, 377),
                'textwidth': 223,
                'textheight': 106}
    elif card_type == 'ice':
        # weyland
        return {'title': (76, 21),
                'subtype': (21, 83),  # vertical
                'strength': (7, 402),  # also vertical
                'cost': (28, 28),
                'text': (68, 73),
                'textwidth': 202,
                'textheight': 150}
    elif card_type == 'operation':
        # jinteki
        return {'title': (83, 20),
                'subtype': (114, 264),
                'cost': (30, 33),
                'text': (40, 292),
                'textwidth': 243,
                'textheight': 103}
    else:
        raise ValueError


SYMBOL_TABLE = {
    '<strong>': '',
    '</strong>': '',
    '<trace>': '',
    '</trace>': ':',
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


def parse_text(text):
    text = re.sub('<errata>.*?</errata>', '', text)

    for symbol, font_char in SYMBOL_TABLE.items():
        text = text.replace(symbol, font_char)
    return text


def make_text_font(size=14):
    return ImageFont.truetype('fonts/minionNR.otf', size=size)


def break_text(draw, fontsize, text, linewidth, max_height):
    """Given a string, a fontsize and an image, intelligently(!) insert
    linebreaks at spaces to keep linewidth where it should be.
    If too tall, shrink font and retry."""

    font = make_text_font(fontsize)
    words = re.split(r'(\s+)', text)

    lines = []
    while words:
        line = words.pop(0)

        while words and (draw.textsize(line + words[0], font=font)[0] < linewidth):
            w = words.pop(0)
            if re.match('\n+', w):
                break
            line += w

        lines.append(line)

    split_text = '\n'.join(lines)
    text_height = draw.textsize(split_text, font=font)[1]
    if text_height > max_height and fontsize > 8:
        return break_text(draw, fontsize-1, text, linewidth, max_height)
    else:
        print(f'fontsize {fontsize} works')
        return split_text, fontsize


edn_path = '/home/karlerik/hobby/netrunner-data/edn/cards/priority-requisition.edn'
orig_img_path = 'original_levy.png'


# load card data

with open(edn_path) as f:
    d = edn_format.edn_parse.parse(f.read())
    card_dict = {pyfy(k): pyfy(v) for k, v in d.items()}

template_path = make_template_path(card_dict['type'], card_dict['faction'])

# make a composite img

template, orig = [Image.open(p).convert('RGBA')
                  for p in [template_path, orig_img_path]]
outimg = orig.resize((template.width, template.height))
outimg.paste(template, mask=template)

# draw text onto it

draw = ImageDraw.Draw(outimg)

black = (0, 0, 0)
gold = (152, 130, 119)
white = (255, 255, 255)

text_locs = get_text_anchors(card_dict['type'], card_dict['faction'])
MISSING_STR = 'VALUE_NOT_HERE'

for item, (fontname, fontsize, fontcolor) in {
        'title': ('Trajan Pro Bold.ttf', 14, black),
        'subtitle': ('Trajan Pro Bold.ttf', 10, black),
        'subtype': ('GillSansStd.otf', 12, black),
        'cost': ('Bank Gothic Medium.otf', 23, white),
        'advancement-requirement': ('Bank Gothic Medium.otf', 30, black),
        'agenda-points': ('Bank Gothic Medium.otf', 30, black),
        'memory-cost': ('Bank Gothic Medium.otf', 14, black),
        'trash-cost': ('Bank Gothic Medium.otf', 20, gold),
        'strength': ('Bank Gothic Medium.otf', 30, black),
        'base-link': ('Bank Gothic Medium.otf', 32, white),
        'minimum-deck-size': ('Bank Gothic Medium.otf', 16, black),
        'influence-limit': ('Bank Gothic Medium.otf', 16, black)
}.items():
    if item == 'subtype':
        text = ' - '.join(map(lambda s: 'AP' if s.lower() == 'ap' else s.replace('-', ' ').title(),
                              card_dict.get('subtype', [])))
    elif item not in ['title', 'subtitle']:
        text = card_dict.get(item, MISSING_STR)
    else:
        if card_dict['type'] == 'identity':
            text = card_dict['title'].split(': ')[0 if item == 'title' else 1]
        else:
            text = card_dict.get(item, MISSING_STR)

    if text == MISSING_STR:
        continue
    if text is None:
        text = 'X'

    pos = text_locs[item]
    font = ImageFont.truetype(f'fonts/{fontname}', size=fontsize)
    if not (card_dict['type'] == 'ice' and item in ['subtype', 'strength']):
        draw.text(pos, str(text), font=font, fill=fontcolor)
    else:
        if item == 'subtype':
            text = 'ICE:  ' + text
        text_width, text_height = draw.textsize(str(text), font=font)
        tmpimg = Image.new('RGBA', tuple([max(text_width, text_height)]*2), color=(0, 0, 0, 0))
        ImageDraw.Draw(tmpimg).text((0, 0), str(text), font=font, fill=fontcolor)
        tmpimg = tmpimg.rotate(90)
        outimg.paste(tmpimg, pos, mask=tmpimg)
        # need to draw text vertically
        pass


# text box is unavoidably special



text, fontsize = break_text(draw, 14, parse_text(card_dict['text']),
                            text_locs['textwidth'], text_locs['textheight'])

draw.text(text_locs['text'], text, font=make_text_font(fontsize), fill=black)


# add inf pips?

outimg.save('out.png')
