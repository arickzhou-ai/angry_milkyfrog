import math
import os
import sys
import pygame
from pygame.locals import *

# 將目前工作目錄切換到這支 .py 檔案所在的資料夾，避免相對路徑找不到圖片
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 狀態流程示意：
# "menu" → (點初始按鈕) → "intro" → (點中間畫面按鈕) → "selecting" (1~5關) → "playing" → (全破) → "win"
#                                                                                       ↑              |
#                                                                                       └─── (重玩) ───┘

# ==================== 初始化與全域變數 ====================
pygame.init()
width, height = 800, 600

pygame.display.set_caption("Pygame")  # 設定視窗標題
windowSurface = pygame.display.set_mode((width, height))  # 建立 800x600 主視窗
windowSurface.fill((55, 55, 55))  # 填入深灰色背景

mainClock = pygame.time.Clock()  # 遊戲時鐘，用來控制 FPS

state = "menu"  # 遊戲狀態："menu"（主選單）、"intro"（中間畫面）、"selecting"（選關）、"playing"（遊玩中）、"win"（全破通關）
level = 1  # 目前所在的關卡編號
completedLevel = 0  # 已通關的最高關卡編號（用來決定後續關卡是否解鎖）

# 主選單「開始遊戲」按鈕位置（左上角座標）
playButton_x = width / 2 - 100
playButton_y = height / 2 - 50

# 中間畫面按鈕位置與大小（放大 1.3 倍：一般 91x91、懸停 104x104）
introButton_scale = 1.3
introButton_w = int(round(70 * introButton_scale))
introButton_h = int(round(70 * introButton_scale))
introButton_hover_w = int(round(80 * introButton_scale))
introButton_hover_h = int(round(80 * introButton_scale))
introButton_x = width / 2 + 100
introButton_y = height / 2 + 50

# 遊玩中/畫面右上角按鈕位置
homeButton_x = width - 100
homeButton_y = 20

# 第 1 ～ 5 關按鈕位置（水平排列，間隔 100px）
level1Button_x = width / 2 - 40 - 200
level1Button_y = 250 - 40

level2Button_x = width / 2 - 40 - 100
level2Button_y = 250 - 40

level3Button_x = width / 2 - 40
level3Button_y = 250 - 40

level4Button_x = width / 2 - 40 + 100
level4Button_y = 250 - 40

level5Button_x = width / 2 - 40 + 200
level5Button_y = 250 - 40

# 通關畫面「再玩一次」按鈕位置
returnButton_x = width / 2 - 100
returnButton_y = height / 2

# chair 大小與位置（放在左下方隊友下方）
chair_w, chair_h = 125, 125
chair_x, chair_y = -10, 325

# Level 2 偏左上角障礙物（obstacle1.png）位置與碰撞箱
obstacle1_x, obstacle1_y = 190, 75
obstacle1_active = False

g = 1  # 重力加速度（每幀對垂直速度 vy 的增量）
partner_angle = 0  # 目前上場夥伴旋轉角度

partnerNumber = 3  # 每關一開始有 3 個可發射的夥伴
enemyNumber = 20  # 預先建立的敵人物件總數上限
boxNumber = 20  # 預先建立的箱子物件總數上限
currentPartnerIdx = 0  # 目前正在待命或飛行中的夥伴索引（0 ~ 2）
stopTimer = 0  # 紀錄目前夥伴速度接近靜止的連續幀數

# 敵人外觀相對於碰撞箱的微調偏移（負值代表往左、往上）
enemy_draw_offset_x = -4
enemy_draw_offset_y = -4

# 未啟用／已淘汰物件的畫面外閒置座標（避免出現在畫面左側）
INACTIVE_X = 2000.0
INACTIVE_Y = 2000.0


def is_obj_spawned(o):
    """判斷 box 或 enemy 是否已配置在關卡中（未啟用時會放在 INACTIVE_X 之外）。"""
    return o["x"] < 1500 and o["x"] > -500


def make_initial_objects(use_split_partners=False):
    """建立包含 3 個夥伴、箱子與敵人的初始物件清單。"""
    partners_init = [
        {
            "x": 35.0 if i == 0 else float(35 - i * 45),
            "y": 280.0 if i == 0 else 410.0,
            "vx": 0.0,
            "vy": 0.0,
            "type": "partner",
            "partner_kind": "split_big" if (use_split_partners and i >= 1) else "normal",
            "slot": i,
            "size": 50,
            "angle": 0.0,
            "active": i == 0,
            "shot": False,
            "gone": False,
            "has_split": False,
        }
        for i in range(partnerNumber)
    ]
    return [
        *partners_init,
        *[
            {
                "x": INACTIVE_X,
                "y": INACTIVE_Y + i * 50,
                "vx": 0.0,
                "vy": 0.0,
                "type": "box",
            }
            for i in range(boxNumber)
        ],
        *[
            {
                "x": INACTIVE_X + 100.0,
                "y": INACTIVE_Y + i * 50,
                "vx": 0.0,
                "vy": 0.0,
                "type": "enemy",
            }
            for i in range(enemyNumber)
        ],
    ]


objects = make_initial_objects()


def all_partners():
    """取得全部夥伴物件清單（包含分裂產生的小夥伴）。"""
    return [o for o in objects if o["type"] == "partner"]


def active_partners():
    """取得目前正在場上或待命中的夥伴清單。"""
    return [
        o
        for o in objects
        if o["type"] == "partner" and not o.get("gone") and o.get("active")
    ]


def partner():
    """取得目前正在上場的主要夥伴物件（供瞄準與發射使用）。"""
    act = active_partners()
    if act:
        return act[0]
    p_list = all_partners()
    if currentPartnerIdx < len(p_list):
        return p_list[currentPartnerIdx]
    return p_list[-1]


def boxes():
    """取得所有型別為 'box' 的箱子物件清單。"""
    return [o for o in objects if o["type"] == "box"]


def enemies():
    """取得所有型別為 'enemy' 的敵人物件清單。"""
    return [o for o in objects if o["type"] == "enemy"]


offset_x = 0  # 畫面固定不移動，鏡頭水平位移恆為 0

isShot = False  # 目前這位夥伴是否已經發射出去
isAiming = False  # 玩家目前是否正在按住滑鼠瞄準

# ==================== 載入並縮放圖片素材 ====================
playButton = pygame.image.load("play_button.png").convert_alpha()
playButton = pygame.transform.scale(playButton, (200, 200))

playButton_hover = pygame.image.load("play_button_hover.png").convert_alpha()
playButton_hover = pygame.transform.scale(playButton_hover, (200, 200))

# 中間畫面的背景與按鈕素材
introBackground = pygame.image.load("intro_background.png")
introBackground = pygame.transform.scale(introBackground, (width, height))

introButton = pygame.image.load("intro_button1.png").convert_alpha()
introButton = pygame.transform.scale(introButton, (introButton_w, introButton_h))

introButton_hover = pygame.image.load("intro_button1.png").convert_alpha()
introButton_hover = pygame.transform.scale(
    introButton_hover, (introButton_hover_w, introButton_hover_h)
)

homeButton = pygame.image.load("home_button.png").convert_alpha()
homeButton = pygame.transform.scale(homeButton, (80, 80))

homeButton_hover = pygame.image.load("home_button_hover.png").convert_alpha()
homeButton_hover = pygame.transform.scale(homeButton_hover, (80, 80))

mainMenuBackground = pygame.image.load("main_menu_background.png")
mainMenuBackground = pygame.transform.scale(mainMenuBackground, (width, height))

levelSelectionBackground = pygame.image.load("level_selection_background.png")
levelSelectionBackground = pygame.transform.scale(
    levelSelectionBackground, (width, height)
)

# 第 1 關按鈕與滑鼠懸停圖
level1Button = pygame.image.load("level1_button.png").convert_alpha()
level1Button = pygame.transform.scale(level1Button, (80, 80))

level1Button_hover = pygame.image.load("level1_button_hover.png").convert_alpha()
level1Button_hover = pygame.transform.scale(level1Button_hover, (80, 80))

# 第 2 關按鈕與滑鼠懸停圖
level2Button = pygame.image.load("level2_button.png").convert_alpha()
level2Button = pygame.transform.scale(level2Button, (80, 80))

level2Button_hover = pygame.image.load("level2_button_hover.png").convert_alpha()
level2Button_hover = pygame.transform.scale(level2Button_hover, (80, 80))

# 第 3 關按鈕與滑鼠懸停圖
level3Button = pygame.image.load("level3_button.png").convert_alpha()
level3Button = pygame.transform.scale(level3Button, (80, 80))

level3Button_hover = pygame.image.load("level3_button_hover.png").convert_alpha()
level3Button_hover = pygame.transform.scale(level3Button_hover, (80, 80))

# 第 4 關按鈕與滑鼠懸停圖
level4Button = pygame.image.load("level4_button.png").convert_alpha()
level4Button = pygame.transform.scale(level4Button, (80, 80))

level4Button_hover = pygame.image.load("level4_button_hover.png").convert_alpha()
level4Button_hover = pygame.transform.scale(level4Button_hover, (80, 80))

# 第 5 關按鈕與滑鼠懸停圖
level5Button = pygame.image.load("level5_button.png").convert_alpha()
level5Button = pygame.transform.scale(level5Button, (80, 80))

level5Button_hover = pygame.image.load("level5_button_hover.png").convert_alpha()
level5Button_hover = pygame.transform.scale(level5Button_hover, (80, 80))

# 未解鎖關卡的鎖定按鈕圖
lockedButton = pygame.image.load("locked_button.png").convert_alpha()
lockedButton = pygame.transform.scale(lockedButton, (80, 80))

# 通關畫面重玩按鈕與滑鼠懸停圖
returnButton = pygame.image.load("again_button.png").convert_alpha()
returnButton = pygame.transform.scale(returnButton, (200, 200))

returnButton_hover = pygame.image.load("again_button_hover.png").convert_alpha()
returnButton_hover = pygame.transform.scale(returnButton_hover, (200, 200))

# 通關結算畫面背景
congratz = pygame.image.load("congratulation.png")
congratz = pygame.transform.scale(congratz, (width, height))

# 背景圖層（天空、地面）
sky = pygame.image.load("sky.png")
sky = pygame.transform.scale(sky, (width, height))

ground = pygame.image.load("ground.png")
ground = pygame.transform.scale(ground, (width, height))

# 椅子、夥伴、分裂夥伴、敵人、箱子素材
chair = pygame.image.load("chair.png").convert_alpha()
chair = pygame.transform.scale(chair, (chair_w, chair_h))

partner_img = pygame.image.load("partner.png").convert_alpha()
partner_img = pygame.transform.scale(partner_img, (50, 50))
rotated_partner = partner_img

split_partner_big_img = pygame.image.load("split_partner_big.png").convert_alpha()
split_partner_big_img = pygame.transform.scale(split_partner_big_img, (50, 50))

split_partner_small_img = pygame.image.load("split_partner_small.png").convert_alpha()
split_partner_small_img = pygame.transform.scale(split_partner_small_img, (34, 34))

enemy_img = pygame.image.load("enemy.png").convert_alpha()
enemy_img = pygame.transform.scale(enemy_img, (50, 50))

box = pygame.image.load("box.png")
box = pygame.transform.scale(box, (40, 40))

# Level 2 障礙物素材（obstacle1.png）：裁切透明邊界並維持原圖比例，避免擠壓與碰撞箱過大
raw_obstacle1 = pygame.image.load("obstacle1.png").convert_alpha()
trim_rect = raw_obstacle1.get_bounding_rect()
if trim_rect.width > 0 and trim_rect.height > 0:
    raw_obstacle1 = raw_obstacle1.subsurface(trim_rect).copy()

orig_obs_w, orig_obs_h = raw_obstacle1.get_size()
obs_scale = min(230 / orig_obs_w, 210 / orig_obs_h)
obstacle1_w = int(round(orig_obs_w * obs_scale))
obstacle1_h = int(round(orig_obs_h * obs_scale))
obstacle1_img = pygame.transform.scale(raw_obstacle1, (obstacle1_w, obstacle1_h))
obstacle1_rect = pygame.Rect(obstacle1_x, obstacle1_y, obstacle1_w, obstacle1_h)

# intro 畫面樹的素材與固定座標
tree_img = pygame.image.load("tree.png").convert_alpha()
tree_img = pygame.transform.scale(tree_img, (36, 48))

intro_trees = [
    (430, 200),
    (280, 310),
    (520, 320),
    (640, 345),
    (400, 500),
    (480, 180),
]

# 爆炸動畫影格（explosion_1.png ～ explosion_5.png）
explosion_frames = [
    pygame.transform.scale(
        pygame.image.load(f"explosion_{i}.png").convert_alpha(), (120, 120)
    )
    for i in range(1, 6)
]
explosions = []  # 進行中的爆炸特效清單，每筆格式：{"x": ..., "y": ..., "frame": 0}


# ==================== 函式定義 ====================
def get_intro_button_rect():
    """取得 intro 畫面按鈕實際貼合圖片（含 1.3 倍縮放）的感應矩形。"""
    base_rect = pygame.Rect(
        int(introButton_x), int(introButton_y), introButton_w, introButton_h
    )
    scaled_w = int(round(introButton_w * introButton_scale))
    scaled_h = int(round(introButton_h * introButton_scale))
    rect = pygame.Rect(0, 0, scaled_w, scaled_h)
    rect.center = base_rect.center
    return rect


def get_partner_base_img(p_obj):
    """依據夥伴類型回傳對應的基礎貼圖。"""
    kind = p_obj.get("partner_kind", "normal")
    if kind == "split_big":
        return split_partner_big_img
    elif kind == "split_small":
        return split_partner_small_img
    return partner_img


def trigger_split_partner():
    """將飛行中的 split_big 夥伴分裂成兩隻 split_small 夥伴。"""
    act_list = active_partners()
    if len(act_list) != 1:
        return False

    big_p = act_list[0]
    if big_p.get("partner_kind") != "split_big" or big_p.get("has_split"):
        return False

    bx, by = big_p["x"], big_p["y"]
    vx, vy = big_p["vx"], big_p["vy"]
    slot = big_p.get("slot", currentPartnerIdx)

    # 讓原本大隻標記消失
    big_p["has_split"] = True
    big_p["gone"] = True
    big_p["active"] = False
    big_p["x"] = -2000.0
    big_p["y"] = -2000.0
    big_p["vx"] = 0.0
    big_p["vy"] = 0.0

    # 生成上下兩隻分裂小夥伴
    small_1 = {
        "x": bx + 8.0,
        "y": by - 14.0,
        "vx": vx * 1.05,
        "vy": vy - 4.5,
        "type": "partner",
        "partner_kind": "split_small",
        "slot": slot,
        "size": 34,
        "angle": big_p.get("angle", 0.0),
        "active": True,
        "shot": True,
        "gone": False,
        "has_split": True,
    }
    small_2 = {
        "x": bx + 8.0,
        "y": by + 18.0,
        "vx": vx * 1.05,
        "vy": vy + 3.5,
        "type": "partner",
        "partner_kind": "split_small",
        "slot": slot,
        "size": 34,
        "angle": big_p.get("angle", 0.0),
        "active": True,
        "shot": True,
        "gone": False,
        "has_split": True,
    }
    objects.insert(0, small_1)
    objects.insert(1, small_2)
    return True


def enemyDie(o):
    """處理敵人死亡：在該位置生成爆炸特效，並把敵人移到畫面外閒置區視為淘汰。"""
    explosions.append({"x": o["x"], "y": o["y"], "frame": 0})
    o["x"] = INACTIVE_X + 100.0
    o["y"] = INACTIVE_Y
    o["vx"] = 0.0
    o["vy"] = 0.0


def resolve_obstacle1_collision(o, obj_w, obj_h):
    """處理單一物件與 Level 2 障礙物碰撞箱（obstacle1_rect）的分離與反彈。"""
    if not obstacle1_active:
        return

    obj_rect = pygame.Rect(o["x"], o["y"], obj_w, obj_h)
    if not obj_rect.colliderect(obstacle1_rect):
        return

    overlap_left = obj_rect.right - obstacle1_rect.left
    overlap_right = obstacle1_rect.right - obj_rect.left
    overlap_top = obj_rect.bottom - obstacle1_rect.top
    overlap_bottom = obstacle1_rect.bottom - obj_rect.top

    min_overlap = min(overlap_left, overlap_right, overlap_top, overlap_bottom)

    if min_overlap == overlap_left:
        o["x"] = float(obstacle1_rect.left - obj_w)
        if o["vx"] > 0:
            o["vx"] *= -0.55
    elif min_overlap == overlap_right:
        o["x"] = float(obstacle1_rect.right)
        if o["vx"] < 0:
            o["vx"] *= -0.55
    elif min_overlap == overlap_top:
        o["y"] = float(obstacle1_rect.top - obj_h)
        if o["vy"] > 0:
            o["vy"] *= -0.45
        o["vx"] *= 0.88
    else:
        o["y"] = float(obstacle1_rect.bottom)
        if o["vy"] < 0:
            o["vy"] *= -0.45


def clamp_to_side_walls():
    """隱形左右邊界牆：擋住場上的夥伴、箱子與敵人，並避免 box 與 enemy 跑到左側。"""
    for o in objects:
        if o["type"] == "partner":
            if o.get("gone") or not o.get("active"):
                continue
            p_size = o.get("size", 50)
            obj_w, obj_h = p_size, p_size
            left_limit = 0
        elif o["type"] == "enemy":
            if not is_obj_spawned(o):
                continue
            obj_w, obj_h = 50, 50
            left_limit = 220
        else:  # box
            if not is_obj_spawned(o):
                continue
            obj_w, obj_h = 40, 40
            left_limit = 220

        right_limit = width - obj_w
        if o["x"] < left_limit:
            o["x"] = left_limit
            if o["vx"] < 0:
                o["vx"] *= -0.4
        elif o["x"] > right_limit:
            o["x"] = right_limit
            if o["vx"] > 0:
                o["vx"] *= -0.4

        resolve_obstacle1_collision(o, obj_w, obj_h)


def reset(use_split_partners=False):
    """重設本關所有物件位置、速度、3 個夥伴佇列與發射/瞄準狀態。"""
    global state, partner_angle, objects, offset_x, isShot, isAiming, currentPartnerIdx, stopTimer, obstacle1_active
    partner_angle = 0
    currentPartnerIdx = 0
    stopTimer = 0
    obstacle1_active = False

    objects = make_initial_objects(use_split_partners=use_split_partners)

    offset_x = 0  # 畫面不移動

    isShot = False
    isAiming = False


def level1():
    """配置第 1 關：x=600 處疊 5 個箱子，上方放 1 位敵人。"""
    reset(use_split_partners=False)
    i = 0
    for o in objects:
        if o["type"] == "box" and i < 5:
            o["x"] = 600
            o["y"] = -i * 50
            i += 1

    enemies()[0]["x"] = 600
    enemies()[0]["y"] = -300


def level2():
    """配置第 2 關：偏左上角放 obstacle1，後面兩隻夥伴為 splitpartner，並在右側配置箱子與敵人。"""
    global obstacle1_active
    reset(use_split_partners=True)
    obstacle1_active = True

    for i in range(1):
        boxes()[i]["y"] = -i * 50
        boxes()[i]["x"] = 500
        i += 1
    for i in range(1, 4):
        boxes()[i]["y"] = -i * 50
        boxes()[i]["x"] = 600
        i += 1
    for i in range(4, 9):
        boxes()[i]["y"] = -i * 50
        boxes()[i]["x"] = 700
        i += 1
    enemies()[0]["x"] = 500
    enemies()[0]["y"] = -200
    enemies()[1]["x"] = 600
    enemies()[1]["y"] = -350
    enemies()[2]["x"] = 700
    enemies()[2]["y"] = -500


def level3():
    """配置第 3 關：斜向排列箱子並搭配敵人與上層箱子結構。"""
    reset(use_split_partners=False)
    i = 0
    for o in objects:
        if o["type"] == "box" and i < 3:
            o["x"] = 550 + i * 40
            o["y"] = -i * 50
            i += 1

    boxes()[3]["x"] = 550
    boxes()[3]["y"] = -150
    enemies()[0]["x"] = 590
    enemies()[0]["y"] = -200
    boxes()[4]["x"] = 630
    boxes()[4]["y"] = -250

    boxes()[5]["x"] = 550
    boxes()[5]["y"] = -200
    boxes()[6]["x"] = 590
    boxes()[6]["y"] = -280
    boxes()[7]["x"] = 630
    boxes()[7]["y"] = -300


def level4():
    """配置第 4 關：左側 x=400 放 8 個箱子，右側搭配與第 3 關類似的結構與敵人。"""
    reset(use_split_partners=False)
    i = 0
    for o in objects:
        if o["type"] == "box" and i < 8:
            o["x"] = 400
            o["y"] = -i * 50
            i += 1
    j = 0
    for o in objects:
        if o["type"] == "box" and j < 3:
            o["x"] = 550 + j * 40
            o["y"] = -j * 50
            j += 1

    boxes()[11]["x"] = 550
    boxes()[11]["y"] = -150
    enemies()[0]["x"] = 590
    enemies()[0]["y"] = -200
    boxes()[12]["x"] = 630
    boxes()[12]["y"] = -250

    boxes()[13]["x"] = 550
    boxes()[13]["y"] = -200
    boxes()[14]["x"] = 590
    boxes()[14]["y"] = -280
    boxes()[15]["x"] = 630
    boxes()[7]["y"] = -300


def level5():
    """配置第 5 關：x=500 放 5 個箱子，兩側 x=400 / x=600 放箱子與 3 位敵人。"""
    reset(use_split_partners=False)
    i = 0
    for o in objects:
        if o["type"] == "box" and i < 5:
            o["x"] = 500
            o["y"] = -i * 50
            i += 1

    boxes()[5]["x"] = 400
    boxes()[5]["y"] = -100
    boxes()[6]["x"] = 600
    boxes()[6]["y"] = -100
    enemies()[0]["x"] = 600
    enemies()[0]["y"] = -200
    enemies()[1]["x"] = 500
    enemies()[1]["y"] = -300
    enemies()[2]["x"] = 400
    enemies()[2]["y"] = -300


def draw_top_right_home_button(mx, my):
    """繪製右上角回上一層/主選單按鈕，並回傳滑鼠是否在按鈕範圍內。"""
    dx = mx - homeButton_x - 40
    dy = my - homeButton_y - 40
    d = math.sqrt(dx**2 + dy**2)
    if d < 40:
        windowSurface.blit(homeButton_hover, (homeButton_x, homeButton_y))
    else:
        windowSurface.blit(homeButton, (homeButton_x, homeButton_y))
    return d < 40


# ==================== 外層主迴圈（關卡載入與全破畫面） ====================
while True:
    # 根據目前關卡編號初始化該關物件配置
    if level == 1:
        level1()
    elif level == 2:
        level2()
    elif level == 3:
        level3()
    elif level == 4:
        level4()
    elif level == 5:
        level5()
    elif level > 5:  # 通過第 5 關後進入全破畫面
        windowSurface.blit(congratz, (0, 0))
        mx, my = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.MOUSEBUTTONUP:
                # 計算滑鼠與「再玩一次」圓形按鈕中心（半徑 100）的距離
                dx = mx - returnButton_x - 100
                dy = my - returnButton_y - 100
                d = math.sqrt(dx**2 + dy**2)
                if d < 100 and event.button == 1:
                    level = 1
                    state = "menu"
                    break

        # 滑鼠懸停時切換按鈕圖示
        dx = mx - returnButton_x - 100
        dy = my - returnButton_y - 100
        d = math.sqrt(dx**2 + dy**2)
        if d < 100:
            windowSurface.blit(returnButton_hover, (returnButton_x, returnButton_y))
        else:
            windowSurface.blit(returnButton, (returnButton_x, returnButton_y))

        pygame.display.update()
        mainClock.tick(60)
        continue  # 跳過下方的關卡遊玩迴圈

    # ==================== 內層遊戲迴圈（選單 / 中間畫面 / 選關 / 遊玩） ====================
    ButtonClicked = False  # 旗標：是否按下了會切換關卡或返回主選單的按鈕
    if state != "win":
        while True:
            # --- 1. 事件處理 ---
            for event in pygame.event.get():
                if event.type == QUIT:
                    pygame.quit()
                    sys.exit()

                if state == "menu":
                    # 主選單：點擊「開始遊戲」後先進入中間畫面 "intro"
                    if event.type == pygame.MOUSEBUTTONUP:
                        mx, my = pygame.mouse.get_pos()

                        dx = mx - playButton_x - 100
                        dy = my - playButton_y - 100
                        d = math.sqrt(dx**2 + dy**2)
                        if d < 100 and event.button == 1:
                            state = "intro"

                elif state == "intro":
                    # 中間畫面：點右上角按鈕回 "menu"；點 introButton 進入 "selecting"
                    if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                        mx, my = pygame.mouse.get_pos()

                        hx = mx - homeButton_x - 40
                        hy = my - homeButton_y - 40
                        if math.sqrt(hx**2 + hy**2) < 40:
                            state = "menu"
                            continue

                        if get_intro_button_rect().collidepoint(mx, my):
                            state = "selecting"

                elif state == "selecting":
                    # 選關畫面：點右上角按鈕回 "intro"；依已通關進度（completedLevel）判斷各關是否可點擊進入
                    if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                        mx, my = pygame.mouse.get_pos()

                        hx = mx - homeButton_x - 40
                        hy = my - homeButton_y - 40
                        if math.sqrt(hx**2 + hy**2) < 40:
                            state = "intro"
                            continue

                        dx1 = mx - level1Button_x - 40
                        dy1 = my - level1Button_y - 40
                        d1 = math.sqrt(dx1**2 + dy1**2)
                        if d1 < 40:
                            level = 1
                            state = "playing"
                            ButtonClicked = True
                            break

                        dx2 = mx - level2Button_x - 40
                        dy2 = my - level2Button_y - 40
                        d2 = math.sqrt(dx2**2 + dy2**2)
                        if d2 < 40 and completedLevel >= 1:
                            level = 2
                            state = "playing"
                            ButtonClicked = True
                            break

                        dx3 = mx - level3Button_x - 40
                        dy3 = my - level3Button_y - 40
                        d3 = math.sqrt(dx3**2 + dy3**2)
                        if d3 < 40 and completedLevel >= 2:
                            level = 3
                            state = "playing"
                            ButtonClicked = True
                            break

                        dx4 = mx - level4Button_x - 40
                        dy4 = my - level4Button_y - 40
                        d4 = math.sqrt(dx4**2 + dy4**2)
                        if d4 < 40 and completedLevel >= 3:
                            level = 4
                            state = "playing"
                            ButtonClicked = True
                            break

                        dx5 = mx - level5Button_x - 40
                        dy5 = my - level5Button_y - 40
                        d5 = math.sqrt(dx5**2 + dy5**2)
                        if d5 < 40 and completedLevel >= 4:
                            level = 5
                            state = "playing"
                            ButtonClicked = True
                            break

                elif state == "playing":
                    # 遊玩中按下滑鼠左鍵：檢查是否點到主選單按鈕；若已發射 split_big 則觸發分裂，否則開始拉弓瞄準
                    if event.type == pygame.MOUSEBUTTONDOWN:
                        if (
                            event.button == 1
                        ):  # 1左鍵、2中鍵、3右鍵、4滾輪上、5滾輪下
                            mx, my = pygame.mouse.get_pos()
                            dx = mx - homeButton_x - 50
                            dy = my - homeButton_y - 50
                            d = math.sqrt(dx**2 + dy**2)

                            if d < 50:
                                state = "menu"
                                ButtonClicked = True
                                break
                            elif isShot:
                                trigger_split_partner()
                            elif currentPartnerIdx < partnerNumber:
                                isAiming = True

                    # 遊玩中放開滑鼠左鍵：依拉扯向量計算目前夥伴初速度並發射
                    if event.type == pygame.MOUSEBUTTONUP:
                        if event.button == 1 and isAiming:
                            mx, my = pygame.mouse.get_pos()
                            cur_p = partner()
                            cur_p["vx"] = (cur_p["x"] + 20 - mx) / 8
                            cur_p["vy"] = (cur_p["y"] + 20 - my) / 8

                            cur_p["shot"] = True
                            isShot = True
                            isAiming = False
                            stopTimer = 0

            # 若切換了關卡或回到主選單，跳出內層迴圈以重新載入關卡/狀態
            if ButtonClicked:
                break

            # --- 2. 遊戲邏輯與物理更新 ---
            if state == "playing":
                offset_x = 0  # 畫面固定不移動

                # 檢查關卡內所有敵人是否都已死亡（已移至畫面外閒置區）
                if all(not is_obj_spawned(o) for o in objects if o["type"] == "enemy"):
                    if level > completedLevel:
                        completedLevel = level
                    level += 1
                    break

                # 若 3 個夥伴都已射完且消失、但敵人還沒死完，重設本關讓玩家再試一次
                if currentPartnerIdx >= partnerNumber:
                    ButtonClicked = True
                    break

                # 發射前將目前上場夥伴固定在起點；發射後套用重力與位移（支援分裂後的兩隻小夥伴）
                if not isShot:
                    cur_p = partner()
                    cur_p["x"] = 35.0
                    cur_p["y"] = 280.0
                    cur_p["angle"] = 0.0
                    partner_angle = 0
                else:
                    for p_obj in active_partners():
                        p_obj["vy"] += g
                        p_obj["x"] += p_obj["vx"]
                        p_obj["y"] += p_obj["vy"]
                        p_obj["angle"] = p_obj.get("angle", 0.0) - p_obj["vx"]
                    if active_partners():
                        partner_angle = active_partners()[0].get("angle", 0.0)

                # 更新已上場的箱子與敵人的重力與位置
                for o in objects:
                    if o["type"] != "partner" and is_obj_spawned(o):
                        o["vy"] += g
                        o["x"] += o["vx"]
                        o["y"] += o["vy"]

                clamp_to_side_walls()

                # 物件兩兩圓形碰撞偵測與位置分離/動量交換（迭代 8 次以穩定堆疊）
                for _ in range(8):
                    for i in range(len(objects)):
                        for j in range(i + 1, len(objects)):
                            a = objects[i]
                            b = objects[j]

                            # 已消失或尚未上場的夥伴不參與碰撞
                            if a["type"] == "partner" and (
                                a.get("gone") or not a.get("active")
                            ):
                                continue
                            if b["type"] == "partner" and (
                                b.get("gone") or not b.get("active")
                            ):
                                continue

                            # 分裂出來的兩隻小夥伴彼此不互相排斥碰撞
                            if (
                                a["type"] == "partner"
                                and b["type"] == "partner"
                                and a.get("partner_kind") == "split_small"
                                and b.get("partner_kind") == "split_small"
                            ):
                                continue

                            # 未上場或已淘汰的 box / enemy 不參與碰撞
                            if a["type"] != "partner" and not is_obj_spawned(a):
                                continue
                            if b["type"] != "partner" and not is_obj_spawned(b):
                                continue

                            ra = (a.get("size", 50) * 0.42) if a["type"] == "partner" else 20.0
                            rb = (b.get("size", 50) * 0.42) if b["type"] == "partner" else 20.0
                            min_dist = ra + rb

                            ca_x = a["x"] + (a.get("size", 50) * 0.5 if a["type"] == "partner" else 20.0)
                            ca_y = a["y"] + (a.get("size", 50) * 0.5 if a["type"] == "partner" else 20.0)
                            cb_x = b["x"] + (b.get("size", 50) * 0.5 if b["type"] == "partner" else 20.0)
                            cb_y = b["y"] + (b.get("size", 50) * 0.5 if b["type"] == "partner" else 20.0)

                            dx = cb_x - ca_x
                            dy = cb_y - ca_y
                            dist_sq = dx**2 + dy**2

                            if dist_sq == 0 or dist_sq >= min_dist**2:
                                continue

                            dist = math.sqrt(dist_sq)
                            nx = dx / dist  # 碰撞法向量 x 分量
                            ny = dy / dist  # 碰撞法向量 y 分量
                            overlap = (min_dist - dist) + 0.5  # 重疊深度加上微小分離緩衝

                            # 將兩物件往相反法向推開
                            a["x"] -= nx * overlap * 0.5
                            a["y"] -= ny * overlap * 0.5
                            b["x"] += nx * overlap * 0.5
                            b["y"] += ny * overlap * 0.5

                            # 計算沿法線方向的速度分量，若正在靠近則交換法向速度
                            va_n = a["vx"] * nx + a["vy"] * ny
                            vb_n = b["vx"] * nx + b["vy"] * ny

                            if va_n - vb_n > 0:
                                a["vx"] += (vb_n - va_n) * nx
                                a["vy"] += (vb_n - va_n) * ny
                                b["vx"] += (va_n - vb_n) * nx
                                b["vy"] += (va_n - vb_n) * ny

                    clamp_to_side_walls()

                # 敵人的死亡判定：檢查所有場上作用中的夥伴（包含分裂出的兩隻小夥伴），或高速摔落地面
                act_p_list = active_partners()
                for o in objects:
                    if o["type"] == "enemy" and is_obj_spawned(o):
                        for p_obj in act_p_list:
                            p_half = p_obj.get("size", 50) * 0.5
                            hit_r = p_half + 23.0
                            dx = (p_obj["x"] + p_half) - (o["x"] + 25)
                            dy = (p_obj["y"] + p_half) - (o["y"] + 25)
                            if math.hypot(dx, dy) < hit_r:
                                enemyDie(o)
                                break

                        if is_obj_spawned(o) and o["y"] >= 410 and o["vy"] > 8:
                            enemyDie(o)

                # 地面碰撞限制（y = 410 為標準 50px 物件地面高度，34px 小夥伴為 y = 426）與水平地面摩擦力
                for o in objects:
                    if o["type"] == "partner":
                        if o.get("gone") or not o.get("active"):
                            continue
                        ground_limit = 460 - o.get("size", 50)
                    elif not is_obj_spawned(o):
                        continue
                    else:
                        ground_limit = 410

                    if o["y"] > ground_limit:
                        o["y"] = ground_limit
                        o["vy"] = 0
                        o["vx"] *= 0.9

                clamp_to_side_walls()

                # 已射出的夥伴只要停住（不論在地面、黑板障礙物上或箱子上）或飛出畫面邊界，就會消失並換下一位夥伴
                if isShot and currentPartnerIdx < partnerNumber:
                    act_p_list = active_partners()
                    all_ready_to_despawn = True

                    for p_obj in act_p_list:
                        speed = math.hypot(p_obj["vx"], p_obj["vy"])
                        out_of_screen = (
                            p_obj["x"] < -150
                            or p_obj["x"] > width + 150
                            or p_obj["y"] > height + 150
                        )
                        # 不再限制必須 y >= 410：只要停在障礙物或箱子上面（speed < 0.4）也算靜止
                        is_stopped = speed < 0.4
                        if not (is_stopped or out_of_screen):
                            all_ready_to_despawn = False
                            break

                    if all_ready_to_despawn:
                        stopTimer += 1
                    else:
                        stopTimer = 0

                    # 停住連續約 10 幀（或全部飛出畫面）就讓目前回合的夥伴消失，並讓下一位上場
                    if stopTimer >= 10:
                        for p_obj in act_p_list:
                            p_obj["gone"] = True
                            p_obj["active"] = False
                            p_obj["x"] = -2000.0
                            p_obj["y"] = -2000.0
                            p_obj["vx"] = 0.0
                            p_obj["vy"] = 0.0

                        currentPartnerIdx += 1
                        stopTimer = 0
                        isShot = False
                        isAiming = False
                        partner_angle = 0

                        next_candidates = [
                            p_obj
                            for p_obj in all_partners()
                            if not p_obj.get("gone") and p_obj.get("slot") == currentPartnerIdx
                        ]
                        if next_candidates:
                            next_p = next_candidates[0]
                            next_p["active"] = True
                            next_p["x"] = 35.0
                            next_p["y"] = 280.0
                            next_p["angle"] = 0.0

                # 推進爆炸動畫影格並移除已播完的特效
                for e in explosions:
                    e["frame"] += 0.3
                explosions = [
                    e for e in explosions if e["frame"] < len(explosion_frames)
                ]

            # --- 3. 畫面繪製 ---
            if state == "menu":
                windowSurface.blit(mainMenuBackground, (0, 0))
                mx, my = pygame.mouse.get_pos()
                dx = mx - playButton_x - 100
                dy = my - playButton_y - 100
                d = math.sqrt(dx**2 + dy**2)

                if d < 100:
                    windowSurface.blit(playButton_hover, (playButton_x, playButton_y))
                else:
                    windowSurface.blit(playButton, (playButton_x, playButton_y))

            elif state == "intro":
                windowSurface.blit(introBackground, (0, 0))

                # 依固定座標畫出所有樹（位於背景之上、按鈕之下）
                for tx, ty in intro_trees:
                    windowSurface.blit(tree_img, (tx, ty))

                mx, my = pygame.mouse.get_pos()
                intro_rect = get_intro_button_rect()

                if intro_rect.collidepoint(mx, my):
                    hover_rect = introButton_hover.get_rect(center=intro_rect.center)
                    windowSurface.blit(introButton_hover, hover_rect.topleft)
                else:
                    draw_rect = introButton.get_rect(center=intro_rect.center)
                    windowSurface.blit(introButton, draw_rect.topleft)

                # 右上角返回主選單按鈕
                draw_top_right_home_button(mx, my)

            elif state == "selecting":
                windowSurface.blit(levelSelectionBackground, (0, 0))
                mx, my = pygame.mouse.get_pos()

                # 右上角返回 intro 按鈕
                draw_top_right_home_button(mx, my)

                # 第 1 關按鈕（預設解鎖）
                dx1 = mx - level1Button_x - 40
                dy1 = my - level1Button_y - 40
                d1 = math.sqrt(dx1**2 + dy1**2)
                if d1 < 40:
                    windowSurface.blit(
                        level1Button_hover, (level1Button_x, level1Button_y)
                    )
                else:
                    windowSurface.blit(level1Button, (level1Button_x, level1Button_y))

                # 第 2 關按鈕（需 completedLevel >= 1）
                dx2 = mx - level2Button_x - 40
                dy2 = my - level2Button_y - 40
                d2 = math.sqrt(dx2**2 + dy2**2)
                if completedLevel >= 1:
                    if d2 < 40:
                        windowSurface.blit(
                            level2Button_hover, (level2Button_x, level2Button_y)
                        )
                    else:
                        windowSurface.blit(
                            level2Button, (level2Button_x, level2Button_y)
                        )
                else:
                    windowSurface.blit(lockedButton, (level2Button_x, level2Button_y))

                # 第 3 關按鈕（需 completedLevel >= 2）
                dx3 = mx - level3Button_x - 40
                dy3 = my - level3Button_y - 40
                d3 = math.sqrt(dx3**2 + dy3**2)
                if completedLevel >= 2:
                    if d3 < 40:
                        windowSurface.blit(
                            level3Button_hover, (level3Button_x, level3Button_y)
                        )
                    else:
                        windowSurface.blit(
                            level3Button, (level3Button_x, level3Button_y)
                        )
                else:
                    windowSurface.blit(lockedButton, (level3Button_x, level3Button_y))

                # 第 4 關按鈕（需 completedLevel >= 3）
                dx4 = mx - level4Button_x - 40
                dy4 = my - level4Button_y - 40
                d4 = math.sqrt(dx4**2 + dy4**2)
                if completedLevel >= 3:
                    if d4 < 40:
                        windowSurface.blit(
                            level4Button_hover, (level4Button_x, level4Button_y)
                        )
                    else:
                        windowSurface.blit(
                            level4Button, (level4Button_x, level4Button_y)
                        )
                else:
                    windowSurface.blit(lockedButton, (level4Button_x, level4Button_y))

                # 第 5 關按鈕（需 completedLevel >= 4）
                dx5 = mx - level5Button_x - 40
                dy5 = my - level5Button_y - 40
                d5 = math.sqrt(dx5**2 + dy5**2)
                if completedLevel >= 4:
                    if d5 < 40:
                        windowSurface.blit(
                            level5Button_hover, (level5Button_x, level5Button_y)
                        )
                    else:
                        windowSurface.blit(
                            level5Button, (level5Button_x, level5Button_y)
                        )
                else:
                    windowSurface.blit(lockedButton, (level5Button_x, level5Button_y))

            elif state == "playing":
                windowSurface.fill((55, 55, 55))

                # 畫面固定不移動，直接繪製天空背景
                for i in range(10):
                    windowSurface.blit(sky, (i * width, 0))

                # 繪製地面與放在隊友下方的 chair
                for i in range(10):
                    windowSurface.blit(ground, (i * width, 450))
                windowSurface.blit(chair, (chair_x, chair_y))

                # 繪製 Level 2 偏左上角障礙物（obstacle1.png，與 obstacle1_rect 完全貼合）
                if obstacle1_active:
                    windowSurface.blit(obstacle1_img, obstacle1_rect.topleft)

                # 繪製已上場的箱子與敵人（敵人的外觀微微往左上偏移，碰撞箱位置維持 o["x"], o["y"]）
                for o in objects:
                    if not is_obj_spawned(o):
                        continue
                    if o["type"] == "box":
                        windowSurface.blit(box, (o["x"], o["y"]))
                    elif o["type"] == "enemy":
                        windowSurface.blit(
                            enemy_img,
                            (
                                o["x"] + enemy_draw_offset_x,
                                o["y"] + enemy_draw_offset_y,
                            ),
                        )

                # 瞄準時繪製 5 顆白色預測軌跡點
                if isAiming and currentPartnerIdx < partnerNumber:
                    mx, my = pygame.mouse.get_pos()
                    cur_p = partner()
                    vx, vy = (
                        cur_p["x"] + 20 - mx,
                        cur_p["y"] + 20 - my,
                    )
                    bx, by = cur_p["x"] + 20, cur_p["y"] + 20

                    n = 5
                    for i in range(n):
                        pygame.draw.circle(
                            windowSurface,
                            (255, 255, 255),
                            (bx + vx / n * (i + 1), by + vy / n * (i + 1)),
                            5,
                        )

                # 繪製尚未消失的夥伴（支援原始 partner、split_partner_big 與分裂後的 split_partner_small）
                for p_obj in all_partners():
                    if p_obj.get("gone"):
                        continue
                    base_img = get_partner_base_img(p_obj)
                    p_half = p_obj.get("size", 50) * 0.5
                    if p_obj.get("active"):
                        rot_img = pygame.transform.rotate(
                            base_img, p_obj.get("angle", 0.0)
                        )
                        rect = rot_img.get_rect(
                            center=(p_obj["x"] + p_half, p_obj["y"] + p_half)
                        )
                        windowSurface.blit(rot_img, rect.topleft)
                    else:
                        windowSurface.blit(base_img, (p_obj["x"], p_obj["y"]))

                # 繪製爆炸特效
                for e in explosions:
                    frame_img = explosion_frames[int(e["frame"])]
                    windowSurface.blit(frame_img, (e["x"] - 40, e["y"] - 40))

                # 繪製右上角回主選單按鈕（含滑鼠懸停效果）
                mx, my = pygame.mouse.get_pos()
                draw_top_right_home_button(mx, my)

            # --- 4. 畫面更新與鎖定 60 FPS ---
            pygame.display.update()
            mainClock.tick(60)