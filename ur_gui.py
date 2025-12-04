import os
import asyncio
import pygame
import random
import math
from typing import List, Tuple, Optional, Dict

# =========================
# Game logic (same rules)
# =========================

class RoyalGameOfUr:
    N_PIECES = 7
    TRACK_LEN = 14

    ROSETTES = {3, 7, 13}
    SHARED = set(range(4, 12))          # 4..11 inclusive
    CAPTURE_SQUARES = SHARED - ROSETTES

    PLAYER_NAMES = ["White", "Black"]
    PLAYER_TOKEN = ["W", "B"]

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)
        # positions[player][piece] = -1 off-board, 0..13 on track, 14 borne off
        self.positions: List[List[int]] = [
            [-1] * self.N_PIECES,
            [-1] * self.N_PIECES
        ]
        self.current_player = 0

    def roll_dice(self) -> int:
        # 4 binary tetrahedral dice ~ 4 fair coins
        return sum(self.rng.choice([0, 1]) for _ in range(4))

    def legal_moves(self, player: int, roll: int) -> List[Tuple[Optional[int], int, bool, Optional[int]]]:
        """
        Return legal moves:
        (piece_index or None for entering new piece, newpos, extra_turn, captured_piece_index)
        """
        if roll == 0:
            return []

        opponent = 1 - player
        moves: List[Tuple[Optional[int], int, bool, Optional[int]]] = []

        # Build quick lookup of own / opponent piece locations on the track
        own_positions = self.positions[player]
        opp_positions = self.positions[opponent]

        own_set = {pos for pos in own_positions if 0 <= pos < self.TRACK_LEN}
        opp_set = {pos for pos in opp_positions if 0 <= pos < self.TRACK_LEN}
        opp_index_by_pos: Dict[int, int] = {}
        for idx, pos in enumerate(opp_positions):
            if 0 <= pos < self.TRACK_LEN and pos not in opp_index_by_pos:
                opp_index_by_pos[pos] = idx

        # Helper: can we land on newpos, and do we capture?
        def landing_info(newpos: int) -> Tuple[bool, Optional[int]]:
            """
            Return (allowed, captured_idx) for moving to newpos.
            - You can never land on your own piece.
            - Opponent pieces only matter on shared squares 4..11.
            - On shared rosettes, you cannot capture.
            """
            if newpos in own_set:
                return False, None

            captured: Optional[int] = None

            # Only shared squares enforce mutual exclusion / capturing
            if newpos in self.SHARED and newpos in opp_set:
                if newpos in self.CAPTURE_SQUARES:
                    captured = opp_index_by_pos[newpos]
                else:
                    # Shared safe square occupied by opponent: cannot land here
                    return False, None

            # On private squares, opponent presence is ignored: both players may
            # occupy the same logical index in their own lane.
            return True, captured

        # Move existing pieces
        for i, pos in enumerate(own_positions):
            if pos < 0 or pos >= self.TRACK_LEN:
                continue
            newpos = pos + roll
            if newpos > self.TRACK_LEN:
                continue
            if newpos == self.TRACK_LEN:
                moves.append((i, newpos, False, None))  # bear off
                continue

            allowed, captured_idx = landing_info(newpos)
            if not allowed:
                continue

            extra = newpos in self.ROSETTES
            moves.append((i, newpos, extra, captured_idx))

        # Enter a new piece from off-board
        if -1 in own_positions:
            entry_pos = roll - 1
            if 0 <= entry_pos < self.TRACK_LEN:
                allowed, captured_idx = landing_info(entry_pos)
                if allowed:
                    extra = entry_pos in self.ROSETTES
                    moves.append((None, entry_pos, extra, captured_idx))

        return moves

    def apply_move(self, player: int, move: Tuple[Optional[int], int, bool, Optional[int]]) -> bool:
        piece_idx, newpos, extra, captured_idx = move
        opponent = 1 - player

        if captured_idx is not None:
            self.positions[opponent][captured_idx] = -1

        if piece_idx is None:
            new_piece = self.positions[player].index(-1)
            self.positions[player][new_piece] = newpos
        else:
            self.positions[player][piece_idx] = newpos

        return extra

    def is_winner(self, player: int) -> bool:
        return all(pos == self.TRACK_LEN for pos in self.positions[player])

# =========================
# Pygame UI
# =========================

# Layout
SQUARE = 72
GAP = 8
# Extra horizontal room for piece racks and counters on left/right of board
MARGIN_X = 210
MARGIN_Y = 60

BOARD_ROWS = 3
BOARD_COLS = 9  # Added one column for bear-off squares

SIDE_PANEL_W = 280
PANEL_GAP = 100  # Gap between board area and side panel
WINDOW_W = MARGIN_X*2 + BOARD_COLS*SQUARE + (BOARD_COLS-1)*GAP + PANEL_GAP + SIDE_PANEL_W
# Extra vertical space so the side-panel quiz UI fits fully on screen
EXTRA_PANEL_H = 220
WINDOW_H = MARGIN_Y*2 + BOARD_ROWS*SQUARE + (BOARD_ROWS-1)*GAP + EXTRA_PANEL_H

# Ancient Mesopotamian color palette - clay, stone, and bronze tones
BG = (45, 35, 25)  # Dark clay/earth
BOARD_BG = (85, 70, 50)  # Light clay tablet
SQ_FILL = (120, 100, 75)  # Clay square
SQ_EDGE = (160, 130, 95)  # Clay edge highlight
HILITE = (255, 215, 50)   # Bright ancient gold highlight
HILITE2 = (70, 130, 200)  # Lapis lazuli blue (ancient precious stone)
ROSETTE = (180, 120, 60)  # Ancient gold/bronze
ROSETTE_DETAIL = (220, 180, 100)  # Bright gold accent

# Piece colors - ivory and ebony inspired
WHITE_PIECE = (240, 230, 210)  # Aged ivory
WHITE_EDGE = (160, 140, 120)  # Darker ivory edge
BLACK_PIECE = (60, 45, 35)  # Dark wood/ebony
BLACK_EDGE = (100, 80, 60)  # Lighter edge

# Text colors
TEXT = (220, 200, 160)  # Warm parchment
MUTED = (140, 120, 90)  # Faded inscription

# =========================
# Mesopotamian quiz content
# =========================

# Only the \"first column\" rosettes (track positions 3 and 7 for both players'
# lanes) trigger a quiz when landed on.
QUIZ_TRIGGER_ROSETTES = {3, 7}

# Each entry: (question, [optionA, optionB, optionC, optionD], correct_index)
QUIZ_QUESTIONS: List[Tuple[str, List[str], int]] = [
    (
        "1. What prompts Ishtar to approach Gilgamesh in Uruk?",
        [
            "A. She needs his help fighting Humbaba",
            "B. She is impressed by his renewed beauty and desire for him grows",
            "C. She wants him to build a temple for her",
            "D. She fears his power and wants a truce",
        ],
        1,
    ),
    (
        "2. Which offer does Ishtar make to persuade Gilgamesh to marry her?",
        [
            "A. A throne in the Netherworld",
            "B. Immortality among the gods",
            "C. A chariot of lapis lazuli and gold and royal honors",
            "D. Control of the Cedar Forest",
        ],
        2,
    ),
    (
        "3. Gilgamesh rejects Ishtar mainly because he:",
        [
            "A. Is already married",
            "B. Swore never to marry a goddess",
            "C. Thinks she is too weak to rule with him",
            "D. Reminds her that she destroys or ruins her lovers",
        ],
        3,
    ),
    (
        "4. Gilgamesh compares Ishtar to several harmful or unreliable things. Which is one of his comparisons?",
        [
            "A. A river that never floods",
            "B. A shoe that bites its owner’s foot",
            "C. A shield that never breaks",
            "D. A tree that bears endless fruit",
        ],
        1,
    ),
    (
        "5. Which former lover of Ishtar does Gilgamesh say she doomed to yearly mourning?",
        [
            "A. Shamash",
            "B. Enkidu",
            "C. Dumuzi",
            "D. Anu",
        ],
        2,
    ),
    (
        "6. What does Gilgamesh claim happened to the shepherd who loved Ishtar?",
        [
            "A. He was turned into a bird",
            "B. He was struck and turned into a wolf",
            "C. He became king of Uruk",
            "D. He was sent to the heavens",
        ],
        1,
    ),
    (
        "7. After being scorned, Ishtar goes to heaven and complains to:",
        [
            "A. Enlil",
            "B. Shamash",
            "C. Lugalbanda",
            "D. Anu",
        ],
        3,
    ),
    (
        "8. What does Ishtar ask Anu to give her?",
        [
            "A. The Tablet of Destinies",
            "B. The Bull of Heaven",
            "C. The Cedar Door",
            "D. A plague for Uruk",
        ],
        1,
    ),
    (
        "9. How does Ishtar threaten Anu if he refuses her request?",
        [
            "A. She will destroy Uruk with fire",
            "B. She will marry another god",
            "C. She will release the dead to consume the living",
            "D. She will overthrow him as king of the gods",
        ],
        2,
    ),
    (
        "10. What condition does Anu set before giving Ishtar the Bull of Heaven?",
        [
            "A. Gilgamesh must apologize publicly",
            "B. Uruk must offer seven temples",
            "C. The widow and farmer of Uruk must be given seven years’ chaff and hay",
            "D. Enkidu must be sacrificed",
        ],
        2,
    ),
    (
        "11. When the Bull of Heaven arrives in Uruk, what disaster happens first?",
        [
            "A. It burns the palace",
            "B. It dries up the natural land and lowers the river level",
            "C. It steals the city’s cattle",
            "D. It knocks down the city walls",
        ],
        1,
    ),
    (
        "12. What happens each time the Bull of Heaven snorts?",
        [
            "A. A storm destroys crops",
            "B. A pit opens and people fall in",
            "C. The gods speak through it",
            "D. Uruk’s gates collapse",
        ],
        1,
    ),
    (
        "13. How do Gilgamesh and Enkidu finally kill the Bull of Heaven?",
        [
            "A. Enkidu traps its horns while Gilgamesh stabs it in a weak spot",
            "B. Gilgamesh shoots it with arrows from the wall",
            "C. They starve it by sealing it in a pit",
            "D. Ishtar withdraws its power and it dies",
        ],
        0,
    ),
    (
        "14. After the Bull is slain, what does Enkidu do to insult Ishtar?",
        [
            "A. He steals her crown",
            "B. He curses her from the temple steps",
            "C. He throws a haunch of the Bull at her and threatens her",
            "D. He refuses to let her mourn",
        ],
        2,
    ),
]

class SquareDef:
    def __init__(self, rect: pygame.Rect, logical_pos: int, owner: Optional[int]):
        self.rect = rect
        self.pos = logical_pos
        self.owner = owner  # 0=White private, 1=Black private, None=shared

def make_board_squares() -> List[SquareDef]:
    squares = []
    # Helper to compute rect from grid coords
    def rect_at(row, col):
        x = MARGIN_X + col * (SQUARE + GAP)
        y = MARGIN_Y + row * (SQUARE + GAP)
        return pygame.Rect(x, y, SQUARE, SQUARE)

    # Shared middle row positions 4..11 mapped to row 1, cols 0..7
    for col in range(8):
        pos = 4 + col
        squares.append(SquareDef(rect_at(1, col), pos, None))

    # White private start positions 0..3 at row 0, cols 0..3
    for col in range(4):
        squares.append(SquareDef(rect_at(0, col), col, 0))

    # White private end positions 12..13 at row 0, cols 6..7
    squares.append(SquareDef(rect_at(0, 6), 12, 0))
    squares.append(SquareDef(rect_at(0, 7), 13, 0))

    # Black private start positions 0..3 at row 2, cols 0..3
    for col in range(4):
        squares.append(SquareDef(rect_at(2, col), col, 1))

    # Black private end positions 12..13 at row 2, cols 6..7
    squares.append(SquareDef(rect_at(2, 6), 12, 1))
    squares.append(SquareDef(rect_at(2, 7), 13, 1))

    # Bear-off squares for both players at position 14 (TRACK_LEN)
    squares.append(SquareDef(rect_at(0, 8), 14, 0))  # White bear-off
    squares.append(SquareDef(rect_at(2, 8), 14, 1))  # Black bear-off

    return squares

def draw_rosette(screen, rect):
    # Ancient Mesopotamian-style rosette with 8-pointed star
    cx, cy = rect.center
    r = rect.width // 4
    
    # Draw layered circular background
    pygame.draw.circle(screen, ROSETTE, (cx, cy), r + 5, 0)
    pygame.draw.circle(screen, ROSETTE_DETAIL, (cx, cy), r + 2, 2)
    
    # Draw 8-pointed star pattern
    import math
    points = []
    for i in range(16):  # Alternating long and short points
        angle = i * math.pi / 8
        radius = (r - 2) if i % 2 == 0 else (r // 2)
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        points.append((x, y))
    
    if len(points) >= 3:
        pygame.draw.polygon(screen, ROSETTE_DETAIL, points)
        pygame.draw.polygon(screen, ROSETTE, points, 2)
    
    # Central dot
    pygame.draw.circle(screen, ROSETTE_DETAIL, (cx, cy), 4, 0)

def draw_piece(screen, rect, player, count_here=1):
    color = WHITE_PIECE if player == 0 else BLACK_PIECE
    edge = WHITE_EDGE if player == 0 else BLACK_EDGE
    cx, cy = rect.center
    radius = rect.width // 3
    
    # Draw main piece with layered effect for depth
    pygame.draw.circle(screen, edge, (cx, cy), radius + 2)  # Shadow/edge
    pygame.draw.circle(screen, color, (cx, cy), radius)     # Main body
    
    # Add ancient texture/carving effect
    inner_radius = radius - 4
    if inner_radius > 0:
        # Carved ring pattern
        pygame.draw.circle(screen, edge, (cx, cy), inner_radius, 2)
        
        # Central symbol - different for each player
        if player == 0:  # White - sun/star symbol
            for i in range(8):
                angle = i * 3.14159 / 4
                x1 = cx + (inner_radius // 2) * math.cos(angle)
                y1 = cy + (inner_radius // 2) * math.sin(angle)
                x2 = cx + (inner_radius // 3) * math.cos(angle)
                y2 = cy + (inner_radius // 3) * math.sin(angle)
                pygame.draw.line(screen, edge, (x1, y1), (x2, y2), 2)
        else:  # Black - crescent/moon symbol
            pygame.draw.circle(screen, edge, (cx - 2, cy), inner_radius // 3, 0)
            pygame.draw.circle(screen, color, (cx, cy), inner_radius // 3, 0)

async def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption("𒌫𒊒 - Royal Game of Ur - Ancient Mesopotamia")
    clock = pygame.time.Clock()

    font = pygame.font.SysFont(None, 28)
    font_big = pygame.font.SysFont(None, 34)

    # Load Bull of Heaven graphic for capture animation
    bull_path = os.path.join(os.path.dirname(__file__), "bull.png")
    bull_img = pygame.image.load(bull_path).convert_alpha()
    bull_size = int(SQUARE * 1.5)
    bull_img = pygame.transform.smoothscale(bull_img, (bull_size, bull_size))

    game = RoyalGameOfUr()
    squares = make_board_squares()

    # UI state machine
    state = "await_roll"   # await_roll, await_select, await_dest, await_continue, await_quiz, game_over
    roll_value = None
    legal_moves = []
    selected_piece: Optional[int] = None  # None => entering offboard piece
    message = "Click Roll to start."

    # Quiz state
    quiz_question_index = 0
    quiz_current: Optional[Tuple[str, List[str], int]] = None
    quiz_player: Optional[int] = None
    quiz_correct_option: Optional[int] = None
    quiz_last_choice: Optional[int] = None
    quiz_feedback_frames = 0

    # Capture animation state (Bull of Heaven)
    CAPTURE_ANIM_FRAMES = 90  # longer bull animation (~1.5s at 60 FPS)
    capture_square: Optional[int] = None
    capture_anim_frames = 0
    post_capture_state: Optional[str] = None
    post_capture_message: str = ""

    # Buttons
    panel_x = MARGIN_X + BOARD_COLS*(SQUARE + GAP) + PANEL_GAP
    roll_btn = pygame.Rect(panel_x, MARGIN_Y + 10, SIDE_PANEL_W - 40, 50)
    cont_btn = pygame.Rect(panel_x, MARGIN_Y + 70, SIDE_PANEL_W - 40, 50)

    # Centered quiz modal layout (appears over board)
    modal_w, modal_h = 620, 360
    quiz_modal_rect = pygame.Rect(
        (WINDOW_W - modal_w) // 2,
        (WINDOW_H - modal_h) // 2,
        modal_w,
        modal_h,
    )

    quiz_btn_width = modal_w - 80
    quiz_btn_height = 40
    quiz_btn_gap = 10
    quiz_btn_y0 = quiz_modal_rect.top + 140
    quiz_answer_rects = [
        pygame.Rect(
            quiz_modal_rect.left + 40,
            quiz_btn_y0 + i * (quiz_btn_height + quiz_btn_gap),
            quiz_btn_width,
            quiz_btn_height,
        )
        for i in range(4)
    ]

    def render_text(text, x, y, big=False, color=TEXT):
        surf = (font_big if big else font).render(text, True, color)
        screen.blit(surf, (x, y))

    def render_multiline(text, x, y, max_width, line_height=20, color=TEXT):
        """Simple word-wrapped text renderer using the regular font."""
        words = text.split()
        line = ""
        for word in words:
            test = (line + " " + word) if line else word
            w, _ = font.size(test)
            if w <= max_width:
                line = test
            else:
                if line:
                    surf = font.render(line, True, color)
                    screen.blit(surf, (x, y))
                    y += line_height
                line = word
        if line:
            surf = font.render(line, True, color)
            screen.blit(surf, (x, y))

    def squares_for_pos(pos: int) -> List[SquareDef]:
        return [s for s in squares if s.pos == pos]

    def current_player_positions_on_track(player: int) -> Dict[int, int]:
        # pos -> piece index
        d = {}
        for i, ppos in enumerate(game.positions[player]):
            if 0 <= ppos < game.TRACK_LEN:
                d[ppos] = i
        return d

    def piece_can_move(piece_idx: Optional[int]) -> bool:
        return any(m[0] == piece_idx for m in legal_moves)

    def moves_for_piece(piece_idx: Optional[int]):
        return [m for m in legal_moves if m[0] == piece_idx]

    def rect_to_logical_pos_and_owner(mx, my) -> Tuple[Optional[int], Optional[int]]:
        for s in squares:
            if s.rect.collidepoint(mx, my):
                return s.pos, s.owner
        return None, None

    running = True
    while running:
        mx, my = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # --- Roll button ---
                if state == "await_roll" and roll_btn.collidepoint(mx, my):
                    roll_value = game.roll_dice()
                    legal_moves = game.legal_moves(game.current_player, roll_value)
                    selected_piece = None

                    if roll_value == 0 or not legal_moves:
                        message = f"Rolled {roll_value}. No legal moves."
                        state = "await_continue"
                    else:
                        message = f"Rolled {roll_value}. Select a piece."
                        state = "await_select"

                # --- Continue button (after no moves) ---
                elif state == "await_continue" and cont_btn.collidepoint(mx, my):
                    game.current_player = 1 - game.current_player
                    roll_value = None
                    legal_moves = []
                    selected_piece = None
                    message = "Click Roll."
                    state = "await_roll"

                # --- Selecting a piece ---
                elif state == "await_select":
                    pos_clicked, owner = rect_to_logical_pos_and_owner(mx, my)
                    p = game.current_player
                    on_track = current_player_positions_on_track(p)

                    # Clicked on-board piece?
                    if pos_clicked is not None:
                        # shared squares accept both players
                        if owner is None or owner == p:
                            if pos_clicked in on_track:
                                piece_idx = on_track[pos_clicked]
                                if piece_can_move(piece_idx):
                                    selected_piece = piece_idx
                                    message = "Select a destination."
                                    state = "await_dest"

                    # Clicked off-board rack?
                    # We'll place racks as circles left side; detect via simple region test.
                    rack_area = pygame.Rect(MARGIN_X - 70, MARGIN_Y, 60, BOARD_ROWS*(SQUARE + GAP))
                    if rack_area.collidepoint(mx, my):
                        if piece_can_move(None):
                            selected_piece = None
                            message = "Select entry destination."
                            state = "await_dest"

                # --- Selecting a destination ---
                elif state == "await_dest":
                    pos_clicked, owner = rect_to_logical_pos_and_owner(mx, my)
                    p = game.current_player
                    move_executed = False

                    if pos_clicked is not None:
                        # Destination must be on shared or current player's private squares
                        if owner is None or owner == p:
                            possible = moves_for_piece(selected_piece)
                            chosen = None
                            for m in possible:
                                if m[1] == pos_clicked:
                                    chosen = m
                                    break

                            if chosen is not None:
                                move_executed = True
                                landing_pos = chosen[1]
                                captured = chosen[3]
                                extra = game.apply_move(p, chosen)
                                legal_moves = []
                                selected_piece = None

                                # Decide what should happen after any capture animation
                                next_state: Optional[str] = None
                                next_message: str = ""

                                if game.is_winner(p):
                                    next_message = f"{game.PLAYER_NAMES[p]} wins!"
                                    next_state = "game_over"
                                else:
                                    # If this was a rosette on a quiz-trigger
                                    # square, start a quiz instead of granting
                                    # the extra roll immediately.
                                    if extra and landing_pos in QUIZ_TRIGGER_ROSETTES:
                                        quiz_player = p
                                        quiz_current = QUIZ_QUESTIONS[quiz_question_index]
                                        quiz_correct_option = quiz_current[2]
                                        next_message = "Quiz time! Answer to see if you earn your extra turn."
                                        next_state = "await_quiz"
                                    else:
                                        if extra:
                                            next_message = "Rosette! Extra turn. Click Roll."
                                            next_state = "await_roll"
                                        else:
                                            game.current_player = 1 - p
                                            next_message = "Turn passes. Click Roll."
                                            next_state = "await_roll"

                                # If a capture occurred, run the Bull of Heaven
                                # animation first, then continue with the
                                # computed next_state / next_message.
                                if captured is not None:
                                    capture_square = landing_pos
                                    capture_anim_frames = CAPTURE_ANIM_FRAMES
                                    post_capture_state = next_state
                                    post_capture_message = next_message
                                    message = "Piece killed by the Bull of Heaven!"
                                    state = "capture_anim"
                                else:
                                    if next_state is not None:
                                        message = next_message
                                        state = next_state

                    # If no move was executed, deselect and go back to piece selection
                    if not move_executed:
                        selected_piece = None
                        message = f"Rolled {roll_value}. Select a piece."
                        state = "await_select"

                # --- Answering a quiz question ---
                elif state == "await_quiz":
                    if quiz_current is not None:
                        for idx, rect in enumerate(quiz_answer_rects):
                            if rect.collidepoint(mx, my):
                                # Next question index for future quizzes
                                quiz_question_index = (quiz_question_index + 1) % len(QUIZ_QUESTIONS)

                                quiz_last_choice = idx
                                if idx == quiz_correct_option:
                                    # Correct: player keeps the rosette extra turn
                                    if quiz_player is not None:
                                        game.current_player = quiz_player
                                    message = "Correct! Extra turn. Click Roll."
                                else:
                                    # Incorrect: extra turn is lost, pass to other player
                                    if quiz_player is not None:
                                        game.current_player = 1 - quiz_player
                                    message = "Incorrect. No extra turn. Click Roll."

                                # Start brief feedback flash before closing quiz
                                quiz_feedback_frames = 30  # ~0.5s at 60 FPS
                                state = "quiz_feedback"
                                break

                elif state == "game_over":
                    # allow restart by clicking Roll
                    if roll_btn.collidepoint(mx, my):
                        game = RoyalGameOfUr()
                        roll_value = None
                        legal_moves = []
                        selected_piece = None
                        message = "New game. Click Roll."
                        state = "await_roll"

        # Countdown capture animation (Bull of Heaven)
        if state == "capture_anim":
            if capture_anim_frames > 0:
                capture_anim_frames -= 1
            if capture_anim_frames <= 0:
                # Finish capture sequence and transition to the queued state
                state = post_capture_state or "await_roll"
                message = post_capture_message or message
                capture_square = None
                post_capture_state = None
                post_capture_message = ""

        # Countdown quiz feedback flash
        if state == "quiz_feedback":
            if quiz_feedback_frames > 0:
                quiz_feedback_frames -= 1
            if quiz_feedback_frames <= 0:
                # Clear quiz state and return to normal flow
                quiz_current = None
                quiz_player = None
                quiz_correct_option = None
                quiz_last_choice = None
                state = "await_roll"

        # =========================
        # Draw
        # =========================
        screen.fill(BG)

        # Ancient clay tablet background with layered stone effect
        board_w = BOARD_COLS*SQUARE + (BOARD_COLS-1)*GAP
        board_h = BOARD_ROWS*SQUARE + (BOARD_ROWS-1)*GAP
        
        # Multiple layers for depth and ancient stone appearance
        tablet_rect = (MARGIN_X-16, MARGIN_Y-16, board_w+32, board_h+32)
        pygame.draw.rect(screen, (60, 45, 30), tablet_rect, border_radius=15)  # Shadow layer
        tablet_rect2 = (MARGIN_X-12, MARGIN_Y-12, board_w+24, board_h+24)
        pygame.draw.rect(screen, BOARD_BG, tablet_rect2, border_radius=12)     # Main tablet
        
        # Ancient border decoration
        pygame.draw.rect(screen, SQ_EDGE, tablet_rect2, 4, border_radius=12)

        # Draw squares with ancient clay tablet texture
        for s in squares:
            # Bear-off squares get special ancient finish styling
            if s.pos == game.TRACK_LEN:  # position 14 = bear-off
                # Clay finish with aged patina
                pygame.draw.rect(screen, (70, 50, 30), s.rect, border_radius=6)
                pygame.draw.rect(screen, (120, 90, 50), s.rect, 3, border_radius=6)
                
                # Ancient cuneiform-style "OFF" marking
                off_text = font.render("⌐", True, (160, 120, 70))  # Cuneiform-like symbol
                text_rect = off_text.get_rect(center=s.rect.center)
                screen.blit(off_text, text_rect)
                
                # Add corner decorations
                corner_size = 8
                corners = [(s.rect.left + 5, s.rect.top + 5),
                          (s.rect.right - 5, s.rect.top + 5),
                          (s.rect.left + 5, s.rect.bottom - 5),
                          (s.rect.right - 5, s.rect.bottom - 5)]
                for corner in corners:
                    pygame.draw.circle(screen, (100, 70, 40), corner, 3)
            else:
                # Base square with clay tablet appearance
                # Multiple layers for depth and texture
                pygame.draw.rect(screen, SQ_EDGE, (s.rect.x - 1, s.rect.y - 1, s.rect.width + 2, s.rect.height + 2), border_radius=8)
                pygame.draw.rect(screen, SQ_FILL, s.rect, border_radius=6)
                
                # Add subtle texture lines (like clay tablet markings)
                texture_color = (SQ_FILL[0] - 15, SQ_FILL[1] - 15, SQ_FILL[2] - 15)
                for i in range(3):
                    y_offset = s.rect.height // 4 * (i + 1)
                    pygame.draw.line(screen, texture_color, 
                                   (s.rect.left + 8, s.rect.top + y_offset),
                                   (s.rect.right - 8, s.rect.top + y_offset), 1)
                
                pygame.draw.rect(screen, SQ_EDGE, s.rect, 2, border_radius=6)

                # rosette marker
                if s.pos in game.ROSETTES:
                    draw_rosette(screen, s.rect)

        # Highlight legal pieces / destinations
        if state in ("await_select", "await_dest"):
            p = game.current_player
            on_track = current_player_positions_on_track(p)

            if state == "await_select":
                # highlight pieces that can move
                for pos, piece_idx in on_track.items():
                    if piece_can_move(piece_idx):
                        for sq in squares_for_pos(pos):
                            if sq.owner is None or sq.owner == p:
                                pygame.draw.rect(screen, HILITE, sq.rect, 5, border_radius=8)
                # highlight offboard rack if enter move exists (only current player's row)
                if piece_can_move(None):
                    rack_y = MARGIN_Y + (0 if p == 0 else 2) * (SQUARE + GAP)
                    # Height covers all 7 stacked pieces: start at rack_y+3, end at rack_y+101
                    rack_rect = pygame.Rect(MARGIN_X - 70, rack_y, 60, 110)
                    pygame.draw.rect(screen, HILITE, rack_rect, 4, border_radius=8)

            if state == "await_dest":
                # highlight destinations for selected piece
                for (_, newpos, _, _) in moves_for_piece(selected_piece):
                    for sq in squares_for_pos(newpos):
                        if sq.owner is None or sq.owner == p:
                            # Special highlighting for bear-off squares
                            if sq.pos == game.TRACK_LEN:
                                pygame.draw.rect(screen, (255, 100, 100), sq.rect, 5, border_radius=8)  # bright red-orange
                            else:
                                pygame.draw.rect(screen, HILITE2, sq.rect, 5, border_radius=8)

        # Draw pieces on squares
        # Iterate per player so that both players can legally occupy the same
        # logical index on their private lanes while still sharing 4..11.
        for p in (0, 1):
            for piece_idx, pos in enumerate(game.positions[p]):
                if 0 <= pos < game.TRACK_LEN:
                    for sq in squares_for_pos(pos):
                        # Draw on shared squares or on the current player's lane
                        if sq.owner is None or sq.owner == p:
                            draw_piece(screen, sq.rect, p)

        # Off-board racks
        for p in (0, 1):
            off_count = game.positions[p].count(-1)
            borne_count = game.positions[p].count(game.TRACK_LEN)

            # Rack positions - left side for waiting pieces
            rack_x = MARGIN_X - 50
            rack_top = MARGIN_Y + (0 if p == 0 else 2)*(SQUARE + GAP)
            counter_y = rack_top + SQUARE // 2 - 10  # Vertically centered with the row
            
            # Left counter: pieces waiting to enter (to the LEFT of pieces)
            left_count_text = font.render(str(off_count), True, TEXT)
            screen.blit(left_count_text, (rack_x - 35, counter_y))
            
            # Ancient-style off-board piece storage
            for i in range(off_count):
                cy = rack_top + 10 + i*14
                piece_color = WHITE_PIECE if p == 0 else BLACK_PIECE
                edge_color = WHITE_EDGE if p == 0 else BLACK_EDGE
                
                # Draw piece with ancient styling
                pygame.draw.circle(screen, edge_color, (rack_x, cy), 7)      # Shadow
                pygame.draw.circle(screen, piece_color, (rack_x, cy), 6)     # Main piece
                pygame.draw.circle(screen, edge_color, (rack_x, cy), 4, 1)   # Inner ring
                
            # Borne-off pieces in ancient style on right
            bx = MARGIN_X + board_w + 50
            for i in range(borne_count):
                by = rack_top + 10 + i*14
                piece_color = WHITE_PIECE if p == 0 else BLACK_PIECE
                edge_color = WHITE_EDGE if p == 0 else BLACK_EDGE
                
                # Ancient victory token style
                pygame.draw.circle(screen, edge_color, (bx, by), 7)
                pygame.draw.circle(screen, piece_color, (bx, by), 6)
                # Victory marking - small star
                pygame.draw.circle(screen, edge_color, (bx, by), 2, 0)
            
            # Right counter: pieces that have crossed/finished (to the RIGHT of pieces)
            right_count_text = font.render(str(borne_count), True, TEXT)
            screen.blit(right_count_text, (bx + 20, counter_y))

        # Course information text below the board
        course_y = MARGIN_Y + board_h + 30
        course_text1 = font.render("NEHC 20004: Mesopotamian Literature (Autumn 2025)", True, MUTED)
        course_text2 = font.render("Professor Paulus", True, MUTED)
        course_x = MARGIN_X + (board_w - course_text1.get_width()) // 2
        screen.blit(course_text1, (course_x, course_y))
        course_x2 = MARGIN_X + (board_w - course_text2.get_width()) // 2
        screen.blit(course_text2, (course_x2, course_y + 25))

        # Bull of Heaven capture animation
        if state == "capture_anim" and capture_square is not None:
            target_squares = squares_for_pos(capture_square)
            if target_squares:
                target_rect = target_squares[0].rect
                tx, ty = target_rect.center

                # Animate bull coming from left side of the board toward target
                progress = 1.0 - (capture_anim_frames / max(1, CAPTURE_ANIM_FRAMES))
                start_x = -bull_size
                x = int(start_x + (tx - start_x) * progress)
                y = ty
                bull_rect = bull_img.get_rect(center=(x, y))
                screen.blit(bull_img, bull_rect)

                # Caption near the target square so it's easy to see
                caption = "Piece killed by the Bull of Heaven!"
                caption_surf = font_big.render(caption, True, TEXT)
                cx = tx - caption_surf.get_width() // 2
                cy = target_rect.top - 40
                if cy < 10:
                    cy = target_rect.bottom + 10
                screen.blit(caption_surf, (cx, cy))

        # Ancient stone side panel with weathered appearance
        panel_rect = pygame.Rect(panel_x - 10, MARGIN_Y - 12, SIDE_PANEL_W, board_h + 24 + EXTRA_PANEL_H)
        
        # Layered stone effect
        shadow_rect = pygame.Rect(panel_x - 8, MARGIN_Y - 10, SIDE_PANEL_W, board_h + 24 + EXTRA_PANEL_H)
        pygame.draw.rect(screen, (35, 25, 15), shadow_rect, border_radius=12)  # Shadow
        pygame.draw.rect(screen, (65, 50, 35), panel_rect, border_radius=12)    # Main panel
        
        # Ancient carved border
        pygame.draw.rect(screen, (90, 70, 45), panel_rect, 3, border_radius=12)
        
        # Add weathering texture
        for i in range(0, panel_rect.height, 20):
            pygame.draw.line(screen, (50, 35, 20),
                           (panel_rect.left + 5, panel_rect.top + i),
                           (panel_rect.right - 5, panel_rect.top + i), 1)

        # Ancient stone buttons
        def draw_button(rect, label, enabled=True):
            if enabled:
                # Raised stone button effect
                shadow_rect = pygame.Rect(rect.x + 2, rect.y + 2, rect.width, rect.height)
                pygame.draw.rect(screen, (40, 30, 20), shadow_rect, border_radius=8)  # Shadow
                pygame.draw.rect(screen, (90, 70, 50), rect, border_radius=8)          # Button face
                pygame.draw.rect(screen, (120, 95, 65), rect, 3, border_radius=8)     # Highlight edge
            else:
                # Pressed/disabled button
                pygame.draw.rect(screen, (55, 40, 25), rect, border_radius=8)
                pygame.draw.rect(screen, (75, 55, 35), rect, 2, border_radius=8)
            
            txt = font_big.render(label, True, TEXT if enabled else MUTED)
            tx = rect.centerx - txt.get_width()//2
            ty = rect.centery - txt.get_height()//2
            screen.blit(txt, (tx, ty))

        draw_button(roll_btn, "Roll", enabled=(state in ("await_roll", "game_over")))
        draw_button(cont_btn, "Continue", enabled=(state == "await_continue"))

        # Panel text
        render_text(f"Turn: {game.PLAYER_NAMES[game.current_player]}", panel_x, MARGIN_Y + 140, big=True)
       

        if roll_value is None:
            render_text("Roll: —", panel_x, MARGIN_Y + 220, big=True)
        else:
            render_text(f"Roll: {roll_value}", panel_x, MARGIN_Y + 220, big=True)

        render_text(message, panel_x, MARGIN_Y + 270)

        if state in ("await_quiz", "quiz_feedback") and quiz_current is not None:
            # Dim the background
            overlay = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            screen.blit(overlay, (0, 0))

            # Quiz modal box in the center
            pygame.draw.rect(screen, (65, 50, 35), quiz_modal_rect, border_radius=12)
            pygame.draw.rect(screen, (120, 95, 65), quiz_modal_rect, 3, border_radius=12)

            question, options, _ = quiz_current
            title_y = quiz_modal_rect.top + 20
            render_text("Quiz:", quiz_modal_rect.left + 20, title_y, big=True)
            render_multiline(
                question,
                quiz_modal_rect.left + 20,
                title_y + 40,
                quiz_modal_rect.width - 40,
            )

            # Draw answer buttons
            for idx, rect in enumerate(quiz_answer_rects):
                if idx < len(options):
                    # Base button color
                    btn_color = (90, 70, 50)
                    border_color = (120, 95, 65)

                    # Highlight selected answer during feedback
                    if state == "quiz_feedback" and quiz_last_choice == idx:
                        if quiz_last_choice is not None and quiz_correct_option is not None:
                            if quiz_last_choice == quiz_correct_option:
                                btn_color = (40, 120, 40)   # green
                                border_color = (20, 200, 20)
                            else:
                                btn_color = (150, 50, 50)   # red
                                border_color = (220, 80, 80)

                    pygame.draw.rect(screen, btn_color, rect, border_radius=8)
                    pygame.draw.rect(screen, border_color, rect, 2, border_radius=8)

                    # Option text
                    opt_text = options[idx]
                    surf = font.render(opt_text, True, TEXT)
                    tx = rect.centerx - surf.get_width() // 2
                    ty = rect.centery - surf.get_height() // 2
                    screen.blit(surf, (tx, ty))
        else:
            # Standard controls help text
            render_text("Instructions:", panel_x, MARGIN_Y + 330, big=True)
            render_text("1) Click Roll", panel_x, MARGIN_Y + 365, color=MUTED)
            render_text("2) Select a piece", panel_x, MARGIN_Y + 390, color=MUTED)
            render_text("3) Choose a new square", panel_x, MARGIN_Y + 415, color=MUTED)

        pygame.display.flip()
        clock.tick(60)
        await asyncio.sleep(0)  # Yield to browser event loop

    pygame.quit()


if __name__ == "__main__":
    asyncio.run(main())
