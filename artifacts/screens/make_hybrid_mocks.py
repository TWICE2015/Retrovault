from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

base_dir = Path('/workspace/artifacts/screens')
out_dir = base_dir

scraper_img = Image.open(base_dir / 'current-scraper-clean-1600x900.png').convert('RGB')
settings_img = Image.open(base_dir / 'current-settings-clean-1600x900.png').convert('RGB')
users_img = Image.open(base_dir / 'current-userspicker-clean-1600x900.png').convert('RGB')

# Fonts
font_bold = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 34)
font_med = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 24)
font_small = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 18)
font_tag = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 20)


def pill(draw, xy, text, fill, stroke=None, text_color=(255,255,255), pad=(14,8), font=font_small):
    x,y=xy
    tw,th = draw.textbbox((0,0), text, font=font)[2:]
    w = tw + pad[0]*2
    h = th + pad[1]*2
    draw.rounded_rectangle((x,y,x+w,y+h), radius=10, fill=fill, outline=stroke, width=2 if stroke else 1)
    draw.text((x+pad[0], y+pad[1]-1), text, font=font, fill=text_color)
    return w,h


def overlay_scraper_old_style(img, density='medium'):
    im = img.copy()
    d = ImageDraw.Draw(im, 'RGBA')

    # top tools bar overlay area
    d.rounded_rectangle((26,86,1576,250), radius=14, fill=(18,18,18,220), outline=(255,255,255,35), width=2)
    d.text((46,98), 'Hybrid metadata controls', font=font_tag, fill=(255,255,255,240))

    # old-style quick actions
    x = 46
    y = 138
    for label, color in [
        ('Scrape All ROMs', (229,9,20,255)),
        ('Missing Art Only', (45,45,45,255)),
        ('Missing Trailers', (45,45,45,255)),
        ('Use Local Artwork', (229,9,20,255)),
        ('Upload local artwork to R2', (45,45,45,255)),
    ]:
        w,h = pill(d, (x,y), label, fill=color, stroke=(255,255,255,48), font=font_small)
        x += w + 12
        if x > 1220:
            x = 46
            y += 52

    # how-it-works block
    text = 'How it works: hash + filename match, then provider fallback.\\nOld dense controls restored for faster batch metadata work.'
    d.rounded_rectangle((46,198,1548,236), radius=8, fill=(0,0,0,120))
    d.text((58,205), text, font=font_small, fill=(190,190,190,255))

    if density == 'high':
        # add compact toggles panel hint
        d.rounded_rectangle((1180,264,1576,420), radius=12, fill=(18,18,18,225), outline=(255,255,255,45), width=2)
        d.text((1200,280), 'Compact Metadata Panel', font=font_tag, fill=(255,255,255,240))
        d.text((1200,314), '• ES-DE local paths', font=font_small, fill=(220,220,220,255))
        d.text((1200,340), '• Override existing URLs', font=font_small, fill=(220,220,220,255))
        d.text((1200,366), '• Batch queue mode', font=font_small, fill=(220,220,220,255))

    return im


def overlay_settings_density(img, mode='balanced'):
    im = img.copy()
    d = ImageDraw.Draw(im, 'RGBA')

    d.rounded_rectangle((980,118,1568,420), radius=14, fill=(20,20,20,218), outline=(255,255,255,42), width=2)
    d.text((1002,136), 'Settings Density Mode', font=font_tag, fill=(255,255,255,245))

    opts = ['Compact', 'Balanced', 'Cinematic']
    x = 1002
    y = 178
    for o in opts:
        active = (o.lower()==mode)
        fill = (229,9,20,255) if active else (42,42,42,255)
        stroke = (255,255,255,70)
        w,h = pill(d, (x,y), o, fill=fill, stroke=stroke, font=font_small)
        x += w + 10

    lines = [
        '• Keep cloud backup + health tools',
        '• Keep users/profile picker integration',
        '• Metadata panel can switch density',
    ]
    yy = 236
    for line in lines:
        d.text((1006,yy), line, font=font_small, fill=(214,214,214,255))
        yy += 30

    if mode == 'compact':
        d.text((1006,330), 'Old-style tighter spacing and utility-first forms.', font=font_small, fill=(255,191,191,255))
    elif mode == 'balanced':
        d.text((1006,330), 'Hybrid default: practical + clean.', font=font_small, fill=(195,235,195,255))
    else:
        d.text((1006,330), 'Netflix-first visuals, tools in collapsible cards.', font=font_small, fill=(195,210,255,255))

    return im


def overlay_users_panel(img, emphasis='balanced'):
    im = img.copy()
    d = ImageDraw.Draw(im, 'RGBA')

    d.rounded_rectangle((34,706,1566,866), radius=14, fill=(18,18,18,222), outline=(255,255,255,45), width=2)
    d.text((58,724), 'Users + Profiles (Hybrid)', font=font_tag, fill=(255,255,255,245))

    if emphasis == 'old':
        msg = 'Simpler profile tools visible in Settings panel, picker optional on boot.'
    elif emphasis == 'new':
        msg = 'Full Netflix Who\'s Watching flow, richer avatars, picker first-class.'
    else:
        msg = 'Netflix picker retained, plus quicker profile edit tools in Settings.'

    d.text((58,760), msg, font=font_med, fill=(222,222,222,255))
    pill(d, (1260,728), 'Keep Who\'s Watching', fill=(229,9,20,255), stroke=(255,255,255,70), font=font_small)
    pill(d, (1260,774), 'Quick Edit in Settings', fill=(52,52,52,255), stroke=(255,255,255,50), font=font_small)

    return im


def make_board(option_name, subtitle, density_mode, users_emphasis, out_name):
    W,H = 1920,1080
    board = Image.new('RGB', (W,H), (14,14,14))
    d = ImageDraw.Draw(board, 'RGBA')

    # Header
    d.rounded_rectangle((24,20,1896,102), radius=14, fill=(20,20,20,245), outline=(255,255,255,40), width=2)
    d.text((44,36), f'{option_name} - Hybrid Preview', font=font_bold, fill=(255,255,255,255))
    d.text((46,74), subtitle, font=font_small, fill=(205,205,205,255))

    # panels positions
    boxes = [
        (24,122,632,1048),
        (656,122,1264,1048),
        (1288,122,1896,1048),
    ]

    # prepare screens
    left = overlay_scraper_old_style(scraper_img.resize((608,926)), density='high' if density_mode=='compact' else 'medium')
    mid = overlay_settings_density(settings_img.resize((608,926)), mode=density_mode)
    right = overlay_users_panel(users_img.resize((608,926)), emphasis=users_emphasis)

    for (x1,y1,x2,y2), im in zip(boxes, [left, mid, right]):
        d.rounded_rectangle((x1,y1,x2,y2), radius=14, fill=(24,24,24,255), outline=(255,255,255,35), width=2)
        board.paste(im, (x1, y1+2))

    # footer choice tag
    tag_color = {
        'Hybrid A': (255,88,88,255),
        'Hybrid B': (82,198,118,255),
        'Hybrid C': (88,150,255,255),
    }.get(option_name, (200,200,200,255))

    d.rounded_rectangle((24,1048,360,1072), radius=8, fill=tag_color)
    d.text((36,1051), f'Pick: {option_name}', font=font_small, fill=(255,255,255,255))

    board.save(out_dir / out_name)


make_board(
    'Hybrid A',
    'Old metadata utility feel + compact settings + simpler profile controls',
    density_mode='compact',
    users_emphasis='old',
    out_name='mock-hybrid-A.png'
)

make_board(
    'Hybrid B',
    'Balanced merge: old metadata utility blocks + modern users + balanced settings density',
    density_mode='balanced',
    users_emphasis='balanced',
    out_name='mock-hybrid-B.png'
)

make_board(
    'Hybrid C',
    'Netflix-first visuals + modern users flow + metadata utility in collapsible cards',
    density_mode='cinematic',
    users_emphasis='new',
    out_name='mock-hybrid-C.png'
)

print('created mocks:', [
    str(out_dir / 'mock-hybrid-A.png'),
    str(out_dir / 'mock-hybrid-B.png'),
    str(out_dir / 'mock-hybrid-C.png'),
])
