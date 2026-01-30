# draw.py
import pygame

# ============================================================
# EASY-TO-CHANGE CONFIG (change values here)
# ============================================================
SCREEN_W, SCREEN_H = 480, 320
OUTER_MARGIN = 5

TOP_RATIO = 0.80			# <-- changed from 0.70 to 0.80
GRID_ROWS, GRID_COLS = 2, 3 # <-- changed from 2x6 to 2x3 (6 squares total)
GRID_GAP = 6				# gap between squares (and around the grid)

# Fonts (easy to change)
SQUARE_FONT_NAME = "Consolas"
INFO_FONT_NAME = "Consolas"
INFO_FONT_SIZE = 24
INFO_FONT_COLOR = (0, 0, 0)

# Bottom text layout (easy to change)
BOTTOM_TEXT_BLOCK_VPAD = 4	 # padding above/below the 2-line block inside bottom area
BOTTOM_TEXT_LEADING = 4		# extra pixels between the two lines (interline)

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)


def _relative_luminance(rgb):
	r, g, b = rgb
	return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _wrap_text_to_width(text, font, max_width):
	words = text.split()
	if not words:
		return [""]

	lines = []
	current = words[0]
	for w in words[1:]:
		test = current + " " + w
		if font.size(test)[0] <= max_width:
			current = test
		else:
			lines.append(current)
			current = w
	lines.append(current)
	return lines


def _fit_font_for_text(text, font_name, rect, max_size=52, min_size=8, padding=6):
	avail_w = max(1, rect.w - 2 * padding)
	avail_h = max(1, rect.h - 2 * padding)

	lo, hi = min_size, max_size
	best = min_size

	while lo <= hi:
		mid = (lo + hi) // 2
		font = pygame.font.SysFont(font_name, mid)
		lines = _wrap_text_to_width(text, font, avail_w)

		widest = max(font.size(line)[0] for line in lines) if lines else 0
		total_h = len(lines) * font.get_linesize()

		if widest <= avail_w and total_h <= avail_h:
			best = mid
			lo = mid + 1
		else:
			hi = mid - 1

	return pygame.font.SysFont(font_name, best)


def _render_multiline_centered(surface, lines, font, color, rect):
	line_h = font.get_linesize()
	total_h = len(lines) * line_h
	y = rect.y + (rect.h - total_h) // 2

	for line in lines:
		img = font.render(line, True, color)
		img_rect = img.get_rect(centerx=rect.centerx, y=y)
		surface.blit(img, img_rect)
		y += line_h


def _ellipsize(text, font, max_width):
	if font.size(text)[0] <= max_width:
		return text

	ell = "…"
	if font.size(ell)[0] > max_width:
		return ""

	lo, hi = 0, len(text)
	best = ""
	while lo <= hi:
		mid = (lo + hi) // 2
		candidate = text[:mid] + ell
		if font.size(candidate)[0] <= max_width:
			best = candidate
			lo = mid + 1
		else:
			hi = mid - 1
	return best


def _draw_justified_triplet(surface, y, line_rect, font, color, left, center, right, padding=2):
	col_w = line_rect.w // 3
	left_rect = pygame.Rect(line_rect.x, y, col_w, line_rect.h)
	center_rect = pygame.Rect(line_rect.x + col_w, y, col_w, line_rect.h)
	right_rect = pygame.Rect(line_rect.x + 2 * col_w, y, line_rect.w - 2 * col_w, line_rect.h)

	left_txt = _ellipsize(left, font, left_rect.w - 2 * padding)
	center_txt = _ellipsize(center, font, center_rect.w - 2 * padding)
	right_txt = _ellipsize(right, font, right_rect.w - 2 * padding)

	if left_txt:
		img = font.render(left_txt, True, color)
		surface.blit(img, (left_rect.x + padding, y + (line_rect.h - img.get_height()) // 2))

	if center_txt:
		img = font.render(center_txt, True, color)
		img_rect = img.get_rect(center=(center_rect.centerx, y + line_rect.h // 2))
		surface.blit(img, img_rect)

	if right_txt:
		img = font.render(right_txt, True, color)
		img_rect = img.get_rect()
		img_rect.midright = (right_rect.right - padding, y + line_rect.h // 2)
		surface.blit(img, img_rect)


def draw_dashboard(
	screen: pygame.Surface,
	squares,				 # list of 6 items: dicts or tuples
	volume_percent: float,
	tempo_bpm: int,
	sound: str,
	prev_song: str,
	current_song: str,
	next_song: str,
):
	screen.fill(WHITE)

	usable = pygame.Rect(
		OUTER_MARGIN,
		OUTER_MARGIN,
		SCREEN_W - 2 * OUTER_MARGIN,
		SCREEN_H - 2 * OUTER_MARGIN
	)

	# ---- Split top/bottom ----
	top_h = int(usable.h * TOP_RATIO)
	bottom_h = usable.h - top_h

	top_rect = pygame.Rect(usable.x, usable.y, usable.w, top_h)
	bottom_rect = pygame.Rect(usable.x, usable.y + top_h, usable.w, bottom_h)

	pygame.draw.line(screen, (220, 220, 220), (usable.x, bottom_rect.y), (usable.right, bottom_rect.y), 1)

	# ============================================================
	# TOP PART: 6 squares (2 rows x 3 cols)
	# ============================================================
	rows, cols = GRID_ROWS, GRID_COLS
	total = rows * cols  # = 6

	norm = []
	for i in range(total):
		if i < len(squares):
			item = squares[i]
			if isinstance(item, dict):
				txt = str(item.get("text", ""))
				bg = item.get("color", (200, 200, 200))
				tc = item.get("text_color", None)
			else:
				txt = str(item[0]) if len(item) > 0 else ""
				bg = item[1] if len(item) > 1 else (200, 200, 200)
				tc = item[2] if len(item) > 2 else None
		else:
			txt, bg, tc = "", (200, 200, 200), None
		norm.append((txt, bg, tc))

	sq_w = (top_rect.w - (cols + 1) * GRID_GAP) // cols
	sq_h = (top_rect.h - (rows + 1) * GRID_GAP) // rows
	sq_w = max(1, sq_w)
	sq_h = max(1, sq_h)

	idx = 0
	for r in range(rows):
		for c in range(cols):
			x = top_rect.x + GRID_GAP + c * (sq_w + GRID_GAP)
			y = top_rect.y + GRID_GAP + r * (sq_h + GRID_GAP)
			rect = pygame.Rect(x, y, sq_w, sq_h)

			txt, bg, tc = norm[idx]
			idx += 1

			pygame.draw.rect(screen, bg, rect, border_radius=6)

			if tc is None:
				tc = BLACK if _relative_luminance(bg) > 140 else WHITE

			font = _fit_font_for_text(txt, SQUARE_FONT_NAME, rect, max_size=52, min_size=8, padding=6)
			lines = _wrap_text_to_width(txt, font, rect.w - 12)
			_render_multiline_centered(screen, lines, font, tc, rect)

	# ============================================================
	# BOTTOM PART: 2 lines of justified text (VERTICALLY CENTERED)
	# ============================================================
	info_font = pygame.font.SysFont(INFO_FONT_NAME, INFO_FONT_SIZE)
	line_h = info_font.get_linesize()

	# Total height of the 2-line block including extra leading between lines
	block_h = (2 * line_h) + BOTTOM_TEXT_LEADING

	# Compute y start so the block is vertically centered within bottom_rect
	# while keeping a small vertical padding inside the bottom area.
	inner = bottom_rect.inflate(0, -2 * BOTTOM_TEXT_BLOCK_VPAD)
	if inner.h <= 0:
		inner = bottom_rect  # fallback

	y_start = inner.y + (inner.h - block_h) // 2

	# Build the line rectangles
	line1_rect = pygame.Rect(bottom_rect.x, y_start, bottom_rect.w, line_h)
	line2_rect = pygame.Rect(bottom_rect.x, y_start + line_h + BOTTOM_TEXT_LEADING, bottom_rect.w, line_h)

	left1 = f"volume {volume_percent:.0f}%"
	center1 = f"{tempo_bpm} BPM"
	right1 = sound

	_draw_justified_triplet(
		screen, line1_rect.y, line1_rect, info_font, INFO_FONT_COLOR,
		left1, center1, right1
	)
	_draw_justified_triplet(
		screen, line2_rect.y, line2_rect, info_font, INFO_FONT_COLOR,
		prev_song, current_song, next_song
	)