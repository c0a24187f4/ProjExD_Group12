import pygame
import sys
import os
import math
import random
from typing import Set

# --- 資料に基づく必須記述 ---
# スクリプトのディレクトリをワーキングディレクトリに設定
try:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
except NameError:
    # (インタラクティブシェルなど、__file__ が定義されていない場合のフォールバック)
    # print("Could not change working directory. Assuming relative paths are correct.")
    pass
# ---------------------------------

# =============================================================================
# 1. config.py の内容 (グローバル定数)
# =============================================================================
# 画面設定
SCREEN_WIDTH = 640
SCREEN_HEIGHT = 720
FPS = 60

# 色の定義
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)

# --- (追加機能用フック) 難易度 ---
# (例: "NORMAL", "HARD")
DIFFICULTY = "NORMAL"
# ----------------------------------


# =============================================================================
# 2. bullet.py の内容 (弾クラス)
# =============================================================================

# --- 自機弾 ---

class PlayerBullet(pygame.sprite.Sprite):
    """
    自機の弾 (ホーミング)
    """
    def __init__(self, pos: tuple[int, int], target: pygame.sprite.Sprite):
        super().__init__()
        try:
            # (ダミー画像)
            self.image = pygame.image.load("data/bullet_player.png").convert_alpha()
            self.image = pygame.transform.scale(self.image, (12, 12))
        except pygame.error:
            self.image = pygame.Surface((10, 10))
            self.image.fill((0, 255, 255))
        
        self.rect = self.image.get_rect(center=pos)
        self.target = target
        self.speed = 8
        self.turn_speed = 3 # ホーミングの追尾性能 (角度)

        # 初期ベクトル (とりあえず上)
        self.dx = 0
        self.dy = -self.speed

    def update(self):
        if self.target.is_active:
            # ターゲットへの角度
            target_dx = self.target.rect.centerx - self.rect.centerx
            target_dy = self.target.rect.centery - self.rect.centery
            target_angle = math.degrees(math.atan2(target_dy, target_dx))
            
            # 現在の角度
            current_angle = math.degrees(math.atan2(self.dy, self.dx))

            # 角度の差
            delta_angle = (target_angle - current_angle + 540) % 360 - 180 # (-180～180の範囲に)

            # 旋回
            if delta_angle > self.turn_speed:
                current_angle += self.turn_speed
            elif delta_angle < -self.turn_speed:
                current_angle -= self.turn_speed
            else:
                current_angle = target_angle
            
            # ベクトル更新
            rad = math.radians(current_angle)
            self.dx = math.cos(rad) * self.speed
            self.dy = math.sin(rad) * self.speed

        self.rect.x += self.dx
        self.rect.y += self.dy

        # 画面外に出たら消去
        if not (0 < self.rect.centerx < SCREEN_WIDTH and 0 < self.rect.centery < SCREEN_HEIGHT):
            self.kill()


# --- 敵弾 ---

class EnemyBullet(pygame.sprite.Sprite):
    """
    敵の弾 (小弾)
    """
    def __init__(self, pos: tuple[int, int], angle: float, speed: float):
        super().__init__()
        try:
            # (ダミー画像)
            self.image = pygame.image.load("data/bullet_enemy_small.png").convert_alpha()
            self.image = pygame.transform.scale(self.image, (10, 10))
        except pygame.error:
            self.image = pygame.Surface((8, 8))
            self.image.fill((255, 100, 100))
        
        self.rect = self.image.get_rect(center=pos)
        
        rad = math.radians(angle)
        self.dx = math.cos(rad) * speed
        self.dy = math.sin(rad) * speed
        
        self.grazed = False # GRAZE判定用フラグ

    def update(self):
        self.rect.x += self.dx
        self.rect.y += self.dy
        # (画面外判定はmain関数側で行う)


class EnemyLargeBullet(EnemyBullet):
    """
    敵の弾 (大弾)
    """
    def __init__(self, pos: tuple[int, int], angle: float, speed: float):
        super().__init__(pos, angle, speed)
        try:
            # (ダミー画像)
            self.image = pygame.image.load("data/bullet_enemy_large.png").convert_alpha()
            self.image = pygame.transform.scale(self.image, (25, 25))
        except pygame.error:
            self.image = pygame.Surface((20, 20))
            self.image.fill((255, 50, 50))
        self.rect = self.image.get_rect(center=pos)


class EnemyLaser(EnemyBullet):
    """
    敵の弾 (細レーザー)
    """
    def __init__(self, pos: tuple[int, int], angle: float, speed: float):
        super().__init__(pos, angle, speed)
        try:
            # (ダミー画像)
            self.original_image = pygame.image.load("data/laser.png").convert_alpha()
            self.original_image = pygame.transform.scale(self.original_image, (100, 5)) # 細長い画像
        except pygame.error:
            self.original_image = pygame.Surface((100, 5))
            self.original_image.fill((255, 200, 0))
        
        # 角度に合わせて画像を回転
        self.image = pygame.transform.rotate(self.original_image, -angle)
        self.rect = self.image.get_rect(center=pos)


class EnemyDelayedLaser(pygame.sprite.Sprite):
    """
    敵の弾 (置きレーザー)
    """
    def __init__(self, pos: tuple[int, int], delay: int, duration: int):
        super().__init__()
        
        self.pos = pos
        self.delay = delay # 発射までの待機フレーム
        self.duration = duration # 発射中のフレーム
        self.timer = 0
        
        self.state = "warning" # 'warning' -> 'active' -> 'finished'
        
        try:
            # (ダミー画像) 予告エフェクト
            self.warn_image = pygame.image.load("data/laser_warning.png").convert_alpha()
            self.warn_image = pygame.transform.scale(self.warn_image, (30, 300))
        except pygame.error:
            self.warn_image = pygame.Surface((30, 300))
            self.warn_image.fill((100, 100, 0))
        
        # 警告画像を半透明にする
        self.warn_image.set_alpha(100) 

        try:
            # (ダミー画像) 本体
            self.active_image = pygame.image.load("data/laser.png").convert_alpha()
            self.active_image = pygame.transform.scale(self.active_image, (30, 300))
        except pygame.error:
            self.active_image = pygame.Surface((30, 300))
            self.active_image.fill((255, 255, 0))

        self.image = self.warn_image
        self.rect = self.image.get_rect(center=self.pos)
        
        self.grazed = False # GRAZE判定用フラグ

    def update(self):
        self.timer += 1
        
        if self.state == "warning":
            # 警告表示（半透明）
            if self.timer > self.delay:
                # 0.5秒経過
                self.state = "active"
                self.image = self.active_image # 実体画像に差し替え
                self.rect = self.image.get_rect(center=self.pos) # 判定を有効化
                self.timer = 0
        
        elif self.state == "active":
            # 実体（当たり判定あり）
            if self.timer > self.duration:
                self.state = "finished"
                self.kill() # 消滅
        
        # 置きレーザーは移動しない


# =============================================================================
# 3. player.py の内容 (自機クラス)
# =============================================================================

class Player(pygame.sprite.Sprite):
    """
    自機クラス
    """
    def __init__(self):
        super().__init__()
        try:
            # (ダミー画像)
            self.image = pygame.image.load("data/player.png").convert_alpha()
            self.image = pygame.transform.scale(self.image, (50, 50)) # サイズ調整
        except pygame.error:
            self.image = pygame.Surface((30, 40))
            self.image.fill((0, 128, 255))
        
        self.rect = self.image.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 50))
        
        # 当たり判定 (イラストより大幅に小さく)
        self.hitbox = pygame.Rect(0, 0, 8, 8)
        self.hitbox.center = self.rect.center

        # GRAZE判定 (hitboxより大きく、イラストより少し小さい)
        self.grazebox = self.rect.inflate(-10, -10) 

        self.speed = 5
        self.lives = 10 # ★変更点: 残機を10に
        self.shoot_delay = 100 # ホーミング弾の発射間隔 (ms)
        self.last_shot = pygame.time.get_ticks()

        # 復活関連
        self.is_respawning = False
        self.respawn_timer = 0
        self.respawn_duration = 10000 # 10秒
        self.blink_timer = 0
        self.is_visible = True

        # --- (追加機能用フック) ---
        # (1) スピードダウン機能用
        self.slow_speed = 2 # Shiftキー押下時の速度
        
        # (2) ボム機能用
        self.bombs = 3 # 初期ボム数
        
        # (3) パワーアップ機能用
        self.power = 1
        self.bullet_power = 1 # 弾の威力
        # ---------------------------

    def update(self, keys: pygame.key.ScancodeWrapper, is_slow: bool, bullets_group: pygame.sprite.Group, target_boss: pygame.sprite.Sprite):
        """
        プレイヤーの更新
        keys: 押されているキーの状態
        is_slow: (追加機能)低速移動フラグ
        bullets_group: 自機弾スプライトグループ
        target_boss: ホーミング対象のボス
        """
        
        if self.is_respawning:
            # 復活待機中 (10秒タイマー)
            now = pygame.time.get_ticks()
            if now - self.respawn_timer > self.respawn_duration:
                self.respawn()
            
            # 点滅処理 (無敵中は操作不可)
            self.blink_timer = (self.blink_timer + 1) % 20
            self.is_visible = self.blink_timer < 10
            self.image.set_alpha(255 if self.is_visible else 0)
            return

        # --- (追加機能フック) 低速移動 ---
        current_speed = self.slow_speed if is_slow else self.speed
        # ---------------------------------

        if keys[pygame.K_w]:
            self.rect.y -= current_speed
        if keys[pygame.K_s]:
            self.rect.y += current_speed
        if keys[pygame.K_a]:
            self.rect.x -= current_speed
        if keys[pygame.K_d]:
            self.rect.x += current_speed

        # 画面端の制限
        self.rect.clamp_ip(pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))
        
        # hitboxとgrazeboxを本体に追従させる
        self.hitbox.center = self.rect.center
        self.grazebox.center = self.rect.center

        # 射撃 (ホーミング)
        self.shoot(bullets_group, target_boss)

    def shoot(self, bullets_group: pygame.sprite.Group, target_boss: pygame.sprite.Sprite):
        """
        ホーミング弾を発射する
        """
        now = pygame.time.get_ticks()
        if now - self.last_shot > self.shoot_delay:
            self.last_shot = now
            
            # --- (追加機能フック) パワーアップ ---
            # パワーに応じて弾の数を増やすなど
            # (例: if self.power > 10: ... )
            # ---------------------------------
            
            new_bullet = PlayerBullet(self.rect.center, target_boss)
            bullets_group.add(new_bullet)

    def hit(self):
        """
        被弾処理
        """
        if not self.is_respawning:
            self.lives -= 1
            self.is_respawning = True
            self.respawn_timer = pygame.time.get_ticks()
            
    def respawn(self):
        """
        復活処理 (SPACEキーまたはタイマー)
        """
        self.is_respawning = False
        self.image.set_alpha(255) # 点滅終了
        self.rect.center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 50)
        self.hitbox.center = self.rect.center
        self.grazebox.center = self.rect.center

    # --- (追加機能フック) ボム ---
    def use_bomb(self) -> bool:
        """
        ボムを使用する。成功したらTrueを返す。
        """
        if self.bombs > 0 and not self.is_respawning:
            self.bombs -= 1
            return True
        return False
    # -----------------------------

    # --- (追加機能フック) パワーアップ ---
    def add_power(self, amount: int):
        """
        パワーアイテムを取得
        """
        self.power += amount
    # ----------------------------------


# =============================================================================
# 4. boss.py の内容 (ボスクラス)
# =============================================================================

class Boss(pygame.sprite.Sprite):
    """
    ボスクラス
    """
    def __init__(self):
        super().__init__()
        try:
            # (ダミー画像)
            self.image = pygame.image.load("data/boss.png").convert_alpha()
            self.image = pygame.transform.scale(self.image, (150, 150))
        except pygame.error:
            self.image = pygame.Surface((100, 100))
            self.image.fill((255, 0, 128))
            
        self.rect = self.image.get_rect(center=(SCREEN_WIDTH // 2, 150))

        # --- (追加機能フック) 難易度 ---
        self.difficulty = DIFFICULTY
        # -----------------------------

        # === ★変更点: HPとタイムの仕様変更 ===
        # スペルカード設定
        # (名前, HP, 弾幕パターンメソッド)
        self.spell_cards = [
            ("スペルカード1「紅色の印」", 100, self.spell_pattern_1),
            ("スペルカード2「蒼色のレーザー」", 150, self.spell_pattern_2),
            ("スペルカード3「金色の悪夢」", 200, self.spell_pattern_3),
        ]
        
        self.current_spell_index = -1
        self.hp = 0
        self.spell_start_time = 0 # ★変更: スペル開始時間 (ms)
        self.clear_times = []     # ★追加: クリアタイム (秒) のリスト
        self.is_active = False
        self.pattern_timer = 0
        
        # === ランダム移動用の変数を追加 ===
        self.move_timer = 0
        self.move_target_pos = self.rect.center
        self.move_speed = 2 # ボスの移動速度

        self.next_spell() # 最初のスペルカードを開始

    def next_spell(self):
        """
        次のスペルカードに移行する
        """
        self.current_spell_index += 1
        if self.current_spell_index < len(self.spell_cards):
            # ★変更: 制限時間(time_limit)を削除
            name, max_hp, pattern_func = self.spell_cards[self.current_spell_index]
            self.hp = max_hp
            self.spell_start_time = pygame.time.get_ticks() # ★変更: 開始時間を記録
            self.current_pattern = pattern_func
            self.is_active = True
            self.pattern_timer = 0 # パターンタイマーリセット
        else:
            # ボス撃破
            self.is_active = False
            self.kill() # ボスを消去

    def update(self, bullets_group: pygame.sprite.Group, player_pos: tuple[int, int]):
        if not self.is_active:
            return

        # ★変更: 制限時間タイマーを削除
        self.pattern_timer += 1
        
        # === ボスのランダム移動処理 ===
        self.move_timer += 1
        if self.move_timer > 90:
            self.move_timer = 0
            target_x = random.randint(100, SCREEN_WIDTH - 100)
            target_y = random.randint(100, 250)
            self.move_target_pos = (target_x, target_y)

        # ターゲットに向かって移動
        dx = self.move_target_pos[0] - self.rect.centerx
        dy = self.move_target_pos[1] - self.rect.centery
        dist = math.hypot(dx, dy)
        
        if dist > self.move_speed:
            self.rect.centerx += (dx / dist) * self.move_speed
            self.rect.centery += (dy / dist) * self.move_speed
        # ===================================

        # スペルカード実行
        self.current_pattern(bullets_group, player_pos)

    def check_spell_transition(self) -> bool:
        """
        ★変更: スペル移行条件 (HPゼロのみ) をチェック
        移行する場合はTrueを返す
        """
        if not self.is_active:
            return False

        # ★変更: タイムアップ(or self.spell_timer <= 0)を削除
        if self.hp <= 0:
            
            # ★追加: クリアタイムを記録
            elapsed_time_ms = pygame.time.get_ticks() - self.spell_start_time
            self.clear_times.append(elapsed_time_ms / 1000.0) # 秒に変換してリストに追加

            # --- (追加機能フック) アイテムドロップ ---
            # self.drop_items(items_group) 
            # --------------------------------------

            self.next_spell()
            return True
        return False

    def hit(self, damage: int):
        if self.is_active:
            self.hp -= damage

    # --- UI用ゲッター ---
    def get_current_spell_name(self) -> str:
        if self.is_active:
            return self.spell_cards[self.current_spell_index][0]
        return ""

    def get_current_spell_max_hp(self) -> int:
        if self.is_active:
            return self.spell_cards[self.current_spell_index][1]
        return 1

    def get_current_elapsed_time(self) -> float:
        """ ★変更: 経過時間を返す (旧 get_time_left) """
        if self.is_active:
            return (pygame.time.get_ticks() - self.spell_start_time) / 1000.0
        return 0.0

    # === 弾幕パターン (弾幕量とランダム性 調整版) ===

    def spell_pattern_1(self, bullets_group: pygame.sprite.Group, player_pos: tuple[int, int]):
        """
        スペル1: 小弾 (小弾と大弾の全方位弾)
        """
        if self.pattern_timer % 60 == 0:
            density = 8
            for i in range(density):
                angle = (360 / density) * i + (self.pattern_timer / 10) + random.uniform(-10, 10)
                speed = 2
                bullets_group.add(EnemyLargeBullet(self.rect.center, angle, speed))
        
        if self.pattern_timer % 12 == 0:
            spread = 10
            angle_to_player = math.degrees(math.atan2(player_pos[1] - self.rect.centery, 
                                                     player_pos[0] - self.rect.centerx))
            for i in range(-1, 2):
                angle = angle_to_player + (i * spread) + random.uniform(-5, 5)
                speed = 4
                bullets_group.add(EnemyBullet(self.rect.center, angle, speed))

    def spell_pattern_2(self, bullets_group: pygame.sprite.Group, player_pos: tuple[int, int]):
        """
        スペル2: レーザー (細レーザーと置きレーザー)
        """
        if self.pattern_timer % 90 == 0:
            count = 2
            for _ in range(count):
                x = random.randint(50, SCREEN_WIDTH - 50)
                y = random.randint(SCREEN_HEIGHT // 2, SCREEN_HEIGHT - 50)
                bullets_group.add(EnemyDelayedLaser((x, y), delay=30, duration=60))

        if self.pattern_timer % 18 == 0:
            angle_to_player = math.degrees(math.atan2(player_pos[1] - self.rect.centery, 
                                                     player_pos[0] - self.rect.centerx))
            bullets_group.add(EnemyLaser(self.rect.center, angle_to_player + random.uniform(-15, 15), 8))

    def spell_pattern_3(self, bullets_group: pygame.sprite.Group, player_pos: tuple[int, int]):
        """
        スペル3: 複合弾幕 (全種類使用)
        """
        if self.pattern_timer % 70 == 0:
            density = 6
            for i in range(density):
                angle = (360 / density) * i - (self.pattern_timer / 20) + random.uniform(-5, 5)
                bullets_group.add(EnemyLargeBullet(self.rect.center, angle, 2))
        
        if self.pattern_timer % 25 == 0:
            angle_to_player = math.degrees(math.atan2(player_pos[1] - self.rect.centery, 
                                                     player_pos[0] - self.rect.centerx))
            bullets_group.add(EnemyBullet(self.rect.center, angle_to_player + random.uniform(-10, 10), 4))
            
        if self.pattern_timer % 50 == 0:
            x = random.randint(50, SCREEN_WIDTH - 50)
            y = random.randint(SCREEN_HEIGHT // 2, SCREEN_HEIGHT - 50)
            bullets_group.add(EnemyDelayedLaser((x, y), delay=30, duration=30))


# =============================================================================
# 5. main.py の内容 (ゲームループとUI)
# =============================================================================

def draw_ui(screen: pygame.Surface, score: int, lives: int, boss: Boss):
    """
    UI（スコア、残機、ボスHPなど）を描画する
    """
    font = pygame.font.Font(None, 36)
    
    # スコア
    score_text = font.render(f"Score: {score}", True, WHITE)
    screen.blit(score_text, (10, 10))
    
    # 残機
    lives_text = font.render(f"Lives: {lives}", True, WHITE)
    screen.blit(lives_text, (10, 40))

    # ボスHP
    if boss.is_active:
        # スペルカード名
        spell_name = boss.get_current_spell_name()
        spell_text = font.render(spell_name, True, WHITE)
        screen.blit(spell_text, (SCREEN_WIDTH // 2 - spell_text.get_width() // 2, 10))

        # HPバー
        hp_ratio = boss.hp / boss.get_current_spell_max_hp()
        hp_bar_width = (SCREEN_WIDTH - 40) * hp_ratio
        pygame.draw.rect(screen, (100, 100, 100), (20, 40, SCREEN_WIDTH - 40, 20))
        pygame.draw.rect(screen, (255, 0, 0), (20, 40, hp_bar_width, 20))

        # ★変更: 経過時間
        elapsed_time = boss.get_current_elapsed_time()
        time_text = font.render(f"Time: {elapsed_time:.2f}", True, WHITE) # 小数点以下2桁
        screen.blit(time_text, (SCREEN_WIDTH - time_text.get_width() - 10, 10))

def draw_game_over(screen: pygame.Surface):
    """ ★追加: ゲームオーバー画面描画 """
    screen.fill(BLACK)
    font = pygame.font.Font(None, 74)
    text = font.render("GAME OVER", True, WHITE)
    screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, SCREEN_HEIGHT // 2 - 50))
    font = pygame.font.Font(None, 40)
    text = font.render("Press SPACE to Exit", True, WHITE)
    screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, SCREEN_HEIGHT // 2 + 20))
    pygame.display.flip()

def draw_results(screen: pygame.Surface, times: list[float]):
    """ ★追加: リザルト画面描画 """
    screen.fill(BLACK)
    font_large = pygame.font.Font(None, 74)
    font_medium = pygame.font.Font(None, 40)
    
    title = font_large.render("Clear!", True, (255, 255, 0)) # 黄色
    screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 80))

    total_time = 0.0
    y_offset = 200
    
    for i, time in enumerate(times):
        text = font_medium.render(f"Spell {i+1}: {time:.2f} sec", True, WHITE)
        screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, y_offset))
        y_offset += 40
        total_time += time

    y_offset += 20 # 少し間隔をあける
    pygame.draw.line(screen, WHITE, (100, y_offset), (SCREEN_WIDTH - 100, y_offset), 2)
    y_offset += 20

    total_text = font_medium.render(f"Total: {total_time:.2f} sec", True, WHITE)
    screen.blit(total_text, (SCREEN_WIDTH // 2 - total_text.get_width() // 2, y_offset))

    y_offset += 100
    continue_text = font_medium.render("Press SPACE to Exit", True, WHITE)
    screen.blit(continue_text, (SCREEN_WIDTH // 2 - continue_text.get_width() // 2, y_offset))
    
    pygame.display.flip()


def main():
    """
    ゲームのメイン関数
    """
    pygame.init()
    # 資料：ミキサーの初期化
    pygame.mixer.init()

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("東方風シューティング (ボスステージ)")
    clock = pygame.time.Clock()

    # [cite_start]--- サウンドの読み込み (資料) --- [cite: 49-58]
    try:
        # BGMの読み込みと再生 (無限ループ)
        pygame.mixer.music.load("data/bgm.mp3")
        pygame.mixer.music.play(loops=-1) #

        # 効果音の読み込み
        se_hit = pygame.mixer.Sound("data/se_hit.wav") #
        se_graze = pygame.mixer.Sound("data/se_graze.wav")
    except pygame.error as e:
        # print(f"サウンドファイルの読み込みに失敗しました: {e}")
        se_hit = None
        se_graze = None
    # ---------------------------------

    # --- スプライトグループの作成 ---
    all_sprites = pygame.sprite.Group()
    player_bullets = pygame.sprite.Group()
    enemy_bullets = pygame.sprite.Group()
    # (追加機能用) アイテムグループ
    # items = pygame.sprite.Group()

    # --- インスタンスの作成 ---
    player = Player()
    boss = Boss()
    all_sprites.add(player, boss)

    # --- ゲーム変数 ---
    score = 0
    game_state = "playing" # ★変更: "playing", "game_over", "results"
    running = True

    # --- メインループ ---
    while running:
        
        # --- イベント処理 ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            # ★変更: ゲーム状態ごとのキー入力
            if game_state == "playing":
                # プレイヤー復活処理
                if player.is_respawning and event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        player.respawn()

                # --- (追加機能用フック) ボムの使用 ---
                # if event.type == pygame.KEYDOWN:
                #     if event.key == pygame.K_x: # (例: Xキーでボム)
                #         if player.use_bomb():
                #             # ボム使用時の処理 (弾幕消去)
                #             for bullet in enemy_bullets:
                #                 bullet.kill()
                #             # (ボムエフェクトの追加など)
                # ------------------------------------

            elif game_state == "game_over":
                # ゲームオーバー画面でSPACEキーを押したら終了
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        running = False # ★変更: コンティニューではなく終了

            elif game_state == "results":
                # リザルト画面でSPACEキーを押したら終了
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        running = False # ★変更: 終了


        # --- 状態ごとの更新・描画処理 ---

        if game_state == "playing":
            # --- 更新処理 ---
            
            # (追加機能用フック) Shiftキーによるスピードダウン
            keys = pygame.key.get_pressed()
            
            # --- ↓ Shift機能実装時の player.update 呼び出し例 ---
            is_slow = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
            player.update(keys, is_slow, player_bullets, boss)
            # ----------------------------------------------------

            boss.update(enemy_bullets, player.rect.center)
            player_bullets.update()
            
            # 敵弾の更新 (画面外に出た弾を消去し、スコア加算)
            avoided_bullets_score = 0
            for bullet in enemy_bullets:
                bullet.update()
                if not screen.get_rect().colliderect(bullet.rect):
                    bullet.kill()
                    # 弾を1つ避けきったらスコア1UP
                    avoided_bullets_score += 1
            score += avoided_bullets_score

            # --- 当たり判定 ---

            # 1. 自機弾 vs ボス
            hits = pygame.sprite.spritecollide(boss, player_bullets, True)
            if hits:
                boss.hit(len(hits) * player.bullet_power) # (パワーアップ機能用に威力を参照)
                # 1ダメージにつきスコア1UP
                score += len(hits) * player.bullet_power

            # 2. 敵弾 vs 自機 (被弾 & GRAZE)
            if not player.is_respawning:
                
                # 2a. GRAZE (かすり) 判定
                graze_list = pygame.sprite.spritecollide(player, enemy_bullets, False, pygame.sprite.collide_rect)
                
                for bullet in graze_list:
                    # 置きレーザーが 'warning' 状態なら判定しない
                    if isinstance(bullet, EnemyDelayedLaser) and bullet.state != "active":
                        continue

                    if not bullet.grazed:
                        if not player.hitbox.colliderect(bullet.rect):
                            score += 20 # GRAZEでスコア20倍 (20UP)
                            bullet.grazed = True
                            if se_graze:
                                se_graze.play()

                # 2b. 被弾判定 (hitbox)
                hit_bullets = []
                for bullet in enemy_bullets:
                    # 置きレーザーが 'warning' 状態なら判定しない
                    if isinstance(bullet, EnemyDelayedLaser) and bullet.state != "active":
                        continue

                    if player.hitbox.colliderect(bullet.rect):
                        hit_bullets.append(bullet)

                if hit_bullets:
                    if se_hit:
                        se_hit.play()
                    
                    player.hit()
                    
                    for bullet in enemy_bullets:
                        bullet.kill()
                    
                    if player.lives <= 0:
                        game_state = "game_over" # ★変更: ゲームオーバー状態に移行

            # 3. スペルカード移行判定
            if boss.check_spell_transition():
                # 移行時に弾幕を消去
                for bullet in enemy_bullets:
                    bullet.kill()
                
                # ★変更: ボス撃破（is_activeがFalse）になったらリザルトへ
                if not boss.is_active:
                    game_state = "results" # リザルト画面に移行
                    # (running = False を削除)

            # --- 描画処理 ---
            screen.fill(BLACK)
            
            all_sprites.draw(screen)
            player_bullets.draw(screen)
            enemy_bullets.draw(screen)
            # items.draw(screen) # (追加機能用)

            # UIの描画
            draw_ui(screen, score, player.lives, boss)
            
            # 復活待機中の表示
            if player.is_respawning:
                font = pygame.font.Font(None, 40)
                text = font.render("Press SPACE to Respawn", True, WHITE)
                screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, SCREEN_HEIGHT // 2 + 100))

            pygame.display.flip()

        elif game_state == "game_over":
            # --- ゲームオーバー画面描画 ---
            draw_game_over(screen)

        elif game_state == "results":
            # --- リザルト画面描画 ---
            draw_results(screen, boss.clear_times)

        clock.tick(FPS)

    pygame.quit()
    sys.exit()


# =============================================================================
# 6. 実行ブロック
# =============================================================================

if __name__ == "__main__":
    main()