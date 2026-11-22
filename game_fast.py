import pygame
import requests
import random
import math
import time
import threading

# ============================================================
# MPU6050 + ESP8266 FLAPPY BIRD
# STABLE Wi-Fi VERSION
# ============================================================

# ------------------------------------------------------------
# CONTROL TUNING  (change these to adjust how the bird feels)
# ------------------------------------------------------------
TILT_GAIN = 0.20      # bird speed per degree of tilt (lower = calmer)
SMOOTHING = 0.25      # 0.1 = very smooth/slow, 0.5 = twitchy
MAX_TARGET = 6.0      # max speed the tilt can ask for
MAX_UP_SPEED = 6.0    # fastest the bird can rise
DEADZONE = 2.0        # degrees of tilt ignored around neutral

ESP_IP = "192.168.1.103"
DATA_URL = f"http://{ESP_IP}/data"

WIDTH, HEIGHT = 1000, 650
FPS = 60

# ============================================================
# PYGAME INITIALIZATION
# ============================================================

pygame.init()

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("MPU FLAPPY - Motion Controlled")

clock = pygame.time.Clock()

# ============================================================
# FONTS
# ============================================================

FONT_BIG = pygame.font.SysFont("arial", 52, bold=True)
FONT_MED = pygame.font.SysFont("arial", 30, bold=True)
FONT_SMALL = pygame.font.SysFont("arial", 20)

# ============================================================
# COLORS
# ============================================================

SKY = (100, 190, 245)
WHITE = (255, 255, 255)
BLACK = (25, 25, 25)
GREEN = (55, 190, 75)
DARK_GREEN = (25, 130, 45)
YELLOW = (255, 220, 40)
ORANGE = (255, 145, 30)
RED = (235, 55, 55)

# ============================================================
# GAME VARIABLES
# ============================================================

bird_x = 220
bird_y = HEIGHT // 2
bird_vy = 0.0
bird_radius = 22

gravity = 0.30
max_fall = 6.5

pipe_width = 90
pipe_gap = 165
pipe_speed = 8.0

pipes = []
particles = []
clouds = []

score = 0
coins = 0
best_score = 0

game_over = False
started = False

last_pipe_x = WIDTH + 150

# ============================================================
# MPU VARIABLES
# ============================================================

pitch = 0.0
roll = 0.0

wifi_ok = False

# ------------------------------------------------------------
# NETWORK SETTINGS
# ------------------------------------------------------------

last_request = 0
REQUEST_INTERVAL = 0.05      # 20 requests/sec

failed_requests = 0
MAX_FAILURES = 5

# ============================================================
# PITCH CALIBRATION
# ============================================================

pitch_center = 0.0
calibrated = False
calibration_samples = []

# ============================================================
# MPU DATA
# ============================================================

session = requests.Session()
last_ok_time = 0.0


def poll_esp():
    """Runs in a background thread so the game never waits on Wi-Fi."""
    global pitch, roll, wifi_ok, failed_requests, last_ok_time

    while True:

        try:

            r = session.get(
                DATA_URL,
                timeout=0.3
            )

            data = r.json()

            pitch = float(data["pitch"])
            roll = float(data["roll"])

            failed_requests = 0
            wifi_ok = True
            last_ok_time = time.time()

            time.sleep(0.005)

        except Exception:

            failed_requests += 1

            if failed_requests >= MAX_FAILURES:
                wifi_ok = False

            time.sleep(0.05)


def get_mpu_data():
    # Used by calibrate(): True while fresh data is arriving
    return (time.time() - last_ok_time) < 0.5


# ============================================================
# CALIBRATION
# ============================================================

def calibrate():

    global pitch_center
    global calibrated

    calibration_samples.clear()

    start = time.time()

    while time.time() - start < 1.5:

        success = get_mpu_data()

        if success:

            calibration_samples.append(pitch)

        # ----------------------------------------------------
        # DRAW CALIBRATION SCREEN
        # ----------------------------------------------------

        screen.fill(SKY)

        title = FONT_BIG.render(
            "CALIBRATING MPU...",
            True,
            BLACK
        )

        screen.blit(
            title,
            (
                WIDTH // 2 - title.get_width() // 2,
                250
            )
        )

        if calibration_samples:

            value = sum(calibration_samples) / len(
                calibration_samples
            )

            txt = FONT_MED.render(
                f"KEEP MPU LEVEL   Pitch: {value:.1f}°",
                True,
                BLACK
            )

            screen.blit(
                txt,
                (
                    WIDTH // 2 - txt.get_width() // 2,
                    320
                )
            )

        else:

            txt = FONT_MED.render(
                "Waiting for ESP8266...",
                True,
                RED
            )

            screen.blit(
                txt,
                (
                    WIDTH // 2 - txt.get_width() // 2,
                    320
                )
            )

        pygame.display.flip()

        clock.tick(30)

        # Don't continuously hammer ESP8266
        time.sleep(0.05)

    # --------------------------------------------------------
    # CALCULATE CENTER
    # --------------------------------------------------------

    if calibration_samples:

        pitch_center = (
            sum(calibration_samples)
            / len(calibration_samples)
        )

        print(
            f"Calibration complete. "
            f"Pitch center = {pitch_center:.2f}"
        )

        calibrated = True

    else:

        print("Calibration failed!")

        calibrated = False


# ============================================================
# PARTICLES
# ============================================================

def create_explosion(x, y):

    for _ in range(35):

        angle = random.uniform(
            0,
            math.pi * 2
        )

        speed = random.uniform(
            2,
            8
        )

        particles.append({

            "x": x,
            "y": y,

            "vx": math.cos(angle) * speed,

            "vy": math.sin(angle) * speed,

            "life": random.randint(
                20,
                45
            ),

            "size": random.randint(
                3,
                8
            )
        })


def update_particles():

    for p in particles[:]:

        p["x"] += p["vx"]

        p["y"] += p["vy"]

        p["vy"] += 0.15

        p["life"] -= 1

        if p["life"] <= 0:

            particles.remove(p)


def draw_particles():

    for p in particles:

        pygame.draw.circle(

            screen,

            ORANGE,

            (
                int(p["x"]),
                int(p["y"])
            ),

            p["size"]
        )


# ============================================================
# CLOUDS
# ============================================================

def create_clouds():

    for _ in range(8):

        clouds.append({

            "x": random.randint(
                0,
                WIDTH
            ),

            "y": random.randint(
                50,
                300
            ),

            "speed": random.uniform(
                0.4,
                1.2
            ),

            "size": random.randint(
                25,
                55
            )
        })


def update_clouds():

    for c in clouds:

        c["x"] -= c["speed"]

        if c["x"] < -100:

            c["x"] = (
                WIDTH
                + random.randint(
                    20,
                    200
                )
            )

            c["y"] = random.randint(
                40,
                300
            )


def draw_clouds():

    for c in clouds:

        x = int(c["x"])
        y = int(c["y"])
        s = c["size"]

        pygame.draw.circle(
            screen,
            WHITE,
            (x, y),
            s
        )

        pygame.draw.circle(
            screen,
            WHITE,
            (
                x + s,
                y + 8
            ),
            int(s * 0.75)
        )

        pygame.draw.circle(
            screen,
            WHITE,
            (
                x - s,
                y + 10
            ),
            int(s * 0.65)
        )

        pygame.draw.ellipse(

            screen,

            WHITE,

            (
                x - s * 1.4,
                y + 5,
                s * 3,
                s
            )
        )


# ============================================================
# PIPES
# ============================================================

def add_pipe():

    gap_y = random.randint(
        150,
        HEIGHT - 180
    )

    pipes.append({

        "x": WIDTH + 50,

        "gap_y": gap_y,

        "passed": False,

        "coin": True
    })


def draw_pipe(x, gap_y):

    # --------------------------------------------------------
    # TOP PIPE
    # --------------------------------------------------------

    top_height = (
        gap_y
        - pipe_gap // 2
    )

    pygame.draw.rect(

        screen,

        DARK_GREEN,

        (
            x,
            0,
            pipe_width,
            top_height
        )
    )

    pygame.draw.rect(

        screen,

        GREEN,

        (
            x + 8,
            0,
            pipe_width - 16,
            top_height
        )
    )

    pygame.draw.rect(

        screen,

        DARK_GREEN,

        (
            x - 8,
            top_height - 25,
            pipe_width + 16,
            25
        )
    )

    # --------------------------------------------------------
    # BOTTOM PIPE
    # --------------------------------------------------------

    bottom_y = (
        gap_y
        + pipe_gap // 2
    )

    pygame.draw.rect(

        screen,

        DARK_GREEN,

        (
            x,
            bottom_y,
            pipe_width,
            HEIGHT - bottom_y
        )
    )

    pygame.draw.rect(

        screen,

        GREEN,

        (
            x + 8,
            bottom_y,
            pipe_width - 16,
            HEIGHT - bottom_y
        )
    )

    pygame.draw.rect(

        screen,

        DARK_GREEN,

        (
            x - 8,
            bottom_y,
            pipe_width + 16,
            25
        )
    )


# ============================================================
# BIRD
# ============================================================

def draw_bird(x, y):

    # Body

    pygame.draw.circle(

        screen,

        YELLOW,

        (
            int(x),
            int(y)
        ),

        bird_radius
    )

    # Wing

    wing_y = int(
        y
        + math.sin(
            time.time() * 15
        ) * 4
    )

    pygame.draw.ellipse(

        screen,

        ORANGE,

        (
            x - 18,
            wing_y - 4,
            25,
            14
        )
    )

    # Eye

    pygame.draw.circle(

        screen,

        WHITE,

        (
            int(x + 8),
            int(y - 8)
        ),

        8
    )

    pygame.draw.circle(

        screen,

        BLACK,

        (
            int(x + 10),
            int(y - 8)
        ),

        3
    )

    # Beak

    pygame.draw.polygon(

        screen,

        ORANGE,

        [

            (
                x + 19,
                y - 2
            ),

            (
                x + 35,
                y + 4
            ),

            (
                x + 19,
                y + 9
            )
        ]
    )


# ============================================================
# RESET GAME
# ============================================================

def reset_game():

    global bird_y
    global bird_vy
    global pipes
    global score
    global coins
    global game_over
    global started
    global pipe_gap
    global pipe_speed
    global last_pipe_x

    bird_y = HEIGHT // 2

    bird_vy = 0

    pipes = []

    particles.clear()

    score = 0

    coins = 0

    pipe_gap = 190

    pipe_speed = 4.2

    last_pipe_x = WIDTH + 150

    game_over = False

    started = False


# ============================================================
# INITIALIZATION
# ============================================================

create_clouds()

running = True

threading.Thread(target=poll_esp, daemon=True).start()

# ------------------------------------------------------------
# INITIAL MPU CALIBRATION
# ------------------------------------------------------------

calibrate()


# ============================================================
# MAIN GAME LOOP
# ============================================================

while running:

    # --------------------------------------------------------
    # 60 FPS GAME LOOP
    # --------------------------------------------------------

    dt = clock.tick(FPS) / 1000.0

    # ========================================================
    # EVENTS
    # ========================================================

    for event in pygame.event.get():

        if event.type == pygame.QUIT:

            running = False

        if event.type == pygame.KEYDOWN:

            # ------------------------------------------------
            # ESC
            # ------------------------------------------------

            if event.key == pygame.K_ESCAPE:

                running = False

            # ------------------------------------------------
            # SPACE
            # ------------------------------------------------

            if event.key == pygame.K_SPACE:

                if game_over:

                    reset_game()

                else:

                    bird_vy = -7.5

                    started = True

            # ------------------------------------------------
            # RECALIBRATE
            # ------------------------------------------------

            if event.key == pygame.K_r:

                reset_game()

                calibrate()

    # ========================================================
    # RELATIVE PITCH
    # ========================================================

    if calibrated:

        relative_pitch = (
            pitch
            - pitch_center
        )

    else:

        relative_pitch = pitch

    # ========================================================
    # MOTION CONTROL
    # ========================================================

    # Tilt UP
    # Bird moves upward

    # Tilt DOWN
    # Bird falls faster

    tilt = relative_pitch

    if abs(tilt) < DEADZONE:
        tilt = 0.0

    target_velocity = tilt * TILT_GAIN

    # Limit MPU influence

    target_velocity = max(
        -MAX_TARGET,
        min(
            MAX_TARGET,
            target_velocity
        )
    )

    # Smooth velocity

    bird_vy += (
        target_velocity
        - bird_vy
    ) * SMOOTHING

    # Gravity

    bird_vy += gravity

    # Limit velocity

    bird_vy = max(
        -MAX_UP_SPEED,
        min(
            max_fall,
            bird_vy
        )
    )

    # Start game automatically
    # if tilt exceeds threshold

    if abs(relative_pitch) > 12:

        started = True

    # ========================================================
    # KEYBOARD BACKUP CONTROL
    # ========================================================

    keys = pygame.key.get_pressed()

    if keys[pygame.K_UP]:

        bird_vy -= 0.7

        started = True

    if keys[pygame.K_DOWN]:

        bird_vy += 0.7

        started = True

    # ========================================================
    # GAME UPDATE
    # ========================================================

    if not game_over and started:

        # ----------------------------------------------------
        # BIRD
        # ----------------------------------------------------

        bird_y += bird_vy

        # ----------------------------------------------------
        # INCREASE DIFFICULTY
        # ----------------------------------------------------

        pipe_speed += 0.0008

        if pipe_speed > 8:

            pipe_speed = 8

        # ----------------------------------------------------
        # SPAWN PIPES
        # ----------------------------------------------------

        if (
            len(pipes) == 0
            or pipes[-1]["x"]
            < WIDTH - 330
        ):

            add_pipe()

        # ----------------------------------------------------
        # MOVE PIPES
        # ----------------------------------------------------

        for pipe in pipes:

            pipe["x"] -= pipe_speed

        # ----------------------------------------------------
        # REMOVE OLD PIPES
        # ----------------------------------------------------

        pipes = [

            p for p in pipes

            if p["x"] > -150
        ]

        # ----------------------------------------------------
        # SCORE
        # ----------------------------------------------------

        for pipe in pipes:

            if (
                not pipe["passed"]
                and
                pipe["x"]
                + pipe_width
                < bird_x
            ):

                pipe["passed"] = True

                score += 1

                # ------------------------------------------------
                # EVERY 5 POINTS
                # MAKE GAME HARDER
                # ------------------------------------------------

                if score % 5 == 0:

                    pipe_gap = max(
                        145,
                        pipe_gap - 5
                    )

        # ====================================================
        # COLLISION
        # ====================================================

        bird_rect = pygame.Rect(

            bird_x
            - bird_radius
            + 4,

            bird_y
            - bird_radius
            + 4,

            bird_radius * 2
            - 8,

            bird_radius * 2
            - 8
        )

        for pipe in pipes:

            # ------------------------------------------------
            # TOP PIPE
            # ------------------------------------------------

            top_rect = pygame.Rect(

                pipe["x"],

                0,

                pipe_width,

                pipe["gap_y"]
                - pipe_gap // 2
            )

            # ------------------------------------------------
            # BOTTOM PIPE
            # ------------------------------------------------

            bottom_rect = pygame.Rect(

                pipe["x"],

                pipe["gap_y"]
                + pipe_gap // 2,

                pipe_width,

                HEIGHT
            )

            # ------------------------------------------------
            # COLLISION
            # ------------------------------------------------

            if (
                bird_rect.colliderect(
                    top_rect
                )
                or
                bird_rect.colliderect(
                    bottom_rect
                )
            ):

                game_over = True

                create_explosion(
                    bird_x,
                    bird_y
                )

        # ====================================================
        # SCREEN COLLISION
        # ====================================================

        if (
            bird_y - bird_radius < 0
            or
            bird_y + bird_radius > HEIGHT
        ):

            game_over = True

            create_explosion(
                bird_x,
                bird_y
            )

    # ========================================================
    # UPDATE PARTICLES
    # ========================================================

    update_particles()

    # ========================================================
    # UPDATE CLOUDS
    # ========================================================

    update_clouds()

    # ========================================================
    # DRAW
    # ========================================================

    screen.fill(SKY)

    # --------------------------------------------------------
    # CLOUDS
    # --------------------------------------------------------

    draw_clouds()

    # --------------------------------------------------------
    # GROUND
    # --------------------------------------------------------

    pygame.draw.rect(

        screen,

        (80, 190, 80),

        (
            0,
            HEIGHT - 25,
            WIDTH,
            25
        )
    )

    pygame.draw.rect(

        screen,

        (220, 200, 100),

        (
            0,
            HEIGHT - 25,
            WIDTH,
            8
        )
    )

    # --------------------------------------------------------
    # PIPES
    # --------------------------------------------------------

    for pipe in pipes:

        draw_pipe(
            pipe["x"],
            pipe["gap_y"]
        )

    # --------------------------------------------------------
    # BIRD
    # --------------------------------------------------------

    if not game_over:

        draw_bird(
            bird_x,
            bird_y
        )

    # --------------------------------------------------------
    # PARTICLES
    # --------------------------------------------------------

    draw_particles()

    # ========================================================
    # HUD
    # ========================================================

    score_text = FONT_MED.render(

        f"SCORE: {score}",

        True,

        BLACK
    )

    screen.blit(
        score_text,
        (25, 20)
    )

    # --------------------------------------------------------
    # PITCH
    # --------------------------------------------------------

    pitch_text = FONT_SMALL.render(

        f"Pitch: {relative_pitch:+.1f}°",

        True,

        BLACK
    )

    screen.blit(
        pitch_text,
        (25, 60)
    )

    # --------------------------------------------------------
    # ROLL
    # --------------------------------------------------------

    roll_text = FONT_SMALL.render(

        f"Roll: {roll:+.1f}°",

        True,

        BLACK
    )

    screen.blit(
        roll_text,
        (25, 88)
    )

    # --------------------------------------------------------
    # SPEED
    # --------------------------------------------------------

    speed_text = FONT_SMALL.render(

        f"Speed: {pipe_speed:.1f}",

        True,

        BLACK
    )

    screen.blit(
        speed_text,
        (25, 116)
    )

    # ========================================================
    # WIFI STATUS
    # ========================================================

    wifi_color = (
        GREEN
        if wifi_ok
        else RED
    )

    if wifi_ok:

        wifi_message = "● MPU Wi-Fi CONNECTED"

    else:

        wifi_message = "● MPU DISCONNECTED"

    wifi_text = FONT_SMALL.render(

        wifi_message,

        True,

        wifi_color
    )

    screen.blit(

        wifi_text,

        (
            WIDTH
            - 270,
            20
        )
    )

    # ========================================================
    # START SCREEN
    # ========================================================

    if (
        not started
        and
        not game_over
    ):

        title = FONT_BIG.render(

            "MPU FLAPPY",

            True,

            BLACK
        )

        screen.blit(

            title,

            (
                WIDTH // 2
                - title.get_width() // 2,

                180
            )
        )

        instruction = FONT_MED.render(

            "TILT UP / DOWN TO FLY",

            True,

            BLACK
        )

        screen.blit(

            instruction,

            (
                WIDTH // 2
                - instruction.get_width() // 2,

                250
            )
        )

        instruction2 = FONT_SMALL.render(

            "SPACE = start/flap   R = recalibrate",

            True,

            BLACK
        )

        screen.blit(

            instruction2,

            (
                WIDTH // 2
                - instruction2.get_width() // 2,

                300
            )
        )

    # ========================================================
    # GAME OVER
    # ========================================================

    if game_over:

        overlay = pygame.Surface(
            (WIDTH, HEIGHT),
            pygame.SRCALPHA
        )

        overlay.fill(
            (0, 0, 0, 100)
        )

        screen.blit(
            overlay,
            (0, 0)
        )

        title = FONT_BIG.render(

            "GAME OVER",

            True,

            WHITE
        )

        screen.blit(

            title,

            (
                WIDTH // 2
                - title.get_width() // 2,

                230
            )
        )

        result = FONT_MED.render(

            f"Score: {score}",

            True,

            WHITE
        )

        screen.blit(

            result,

            (
                WIDTH // 2
                - result.get_width() // 2,

                300
            )
        )

        restart = FONT_SMALL.render(

            "Press SPACE to restart",

            True,

            WHITE
        )

        screen.blit(

            restart,

            (
                WIDTH // 2
                - restart.get_width() // 2,

                350
            )
        )

    # ========================================================
    # UPDATE DISPLAY
    # ========================================================

    pygame.display.flip()


# ============================================================
# EXIT
# ============================================================

pygame.quit()