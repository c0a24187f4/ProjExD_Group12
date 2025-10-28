import pygame
import sys
import os
import math
import random
from typing import Set

# 資料に基づく必須記述
# スクリプトのディレクトリをワーキングディレクトリに設定
try:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
except NameError:
    # (インタラクティブシェルなど、__file__ が定義されていない場合のフォールバック)
    pass


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
        except (pygame.error, FileNotFoundError):
            self.image = pygame.Surface((10, 10))
            self.image.fill((0, 255, 255))
        
        self.rect = self.image.get_rect(center=pos)
        self.target = target
        self.speed = 8
        self.turn_speed = 3  # ホーミングの追尾性能 (角度)

        # 初期ベクトル (とりあえず上)
        self.dx = 0
        self.dy = -self.speed

    def update(self):
        # ターゲット参照は安全に（target が None や属性を持たない場合を考慮）
        if getattr(self.target, "is_active", False) or getattr(self.target, "is_ex_stage", False):
            # ターゲットへの角度
            target_dx = self.target.rect.centerx - self.rect.centerx
            target_dy = self.target.rect.centery - self.rect.centery
            target_angle = math.degrees(math.atan2(target_dy, target_dx))
            
            # 現在の角度
            current_angle = math.degrees(math.atan2(self.dy, self.dx))

            # 角度の差
            delta_angle = (target_angle - current_angle + 540) % 360 - 180  # (-180～180の範囲に)

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
        except (pygame.error, FileNotFoundError):
            self.image = pygame.Surface((8, 8))
            self.image.fill((255, 100, 100))
        
        self.rect = self.image.get_rect(center=pos)
        
        rad = math.radians(angle)
        self.dx = math.cos(rad) * speed
        self.dy = math.sin(rad) * speed
        
        self.grazed = False  # GRAZE判定用フラグ

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
        except (pygame.error, FileNotFoundError):
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
            self.original_image = pygame.transform.scale(self.original_image, (100, 5))  # 細長い画像
        except (pygame.error, FileNotFoundError):
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
        self.delay = delay  # 発射までの待機フレーム
        self.duration = duration  # 発射中のフレーム
        self.timer = 0
        
        self.state = "warning"  # 'warning' -> 'active' -> 'finished'
        
        try:
            # (ダミー画像) 予告エフェクト
            self.warn_image = pygame.image.load("data/laser_warning.png").convert_alpha()
            self.warn_image = pygame.transform.scale(self.warn_image, (30, 300))
        except (pygame.error, FileNotFoundError):
            self.warn_image = pygame.Surface((30, 300))
            self.warn_image.fill((100, 100, 0))
        
        # 警告画像を半透明にする
        self.warn_image.set_alpha(100) 

        try:
            # (ダミー画像) 本体
            self.active_image = pygame.image.load("data/laser.png").convert_alpha()
            self.active_image = pygame.transform.scale(self.active_image, (30, 300))
        except (pygame.error, FileNotFoundError):
            self.active_image = pygame.Surface((30, 300))
            self.active_image.fill((255, 255, 0))

        self.image = self.warn_image
        self.rect = self.image.get_rect(center=self.pos)
        
        self.grazed = False  # GRAZE判定用フラグ

    def update(self):
        self.timer += 1
        
        if self.state == "warning":
            # 警告表示（半透明）
            if self.timer > self.delay:
                # 0.5秒経過
                self.state = "active"
                self.image = self.active_image  # 実体画像に差し替え
                self.rect = self.image.get_rect(center=self.pos)  # 判定を有効化
                self.timer = 0
        
        elif self.state == "active":
            # 実体（当たり判定あり）
            if self.timer > self.duration:
                self.state = "finished"
                self.kill()  # 消滅
        # 置きレーザーは移動しない


# ---------------------------
# EX専用: 特大弾クラス
# ---------------------------
class EnemyHugeBullet(EnemyBullet):
    """
    敵の弾 (特大弾) - EX専用
    """
    def __init__(self, pos: tuple[int, int], angle: float, speed: float):
        # 注意: EnemyBullet.__init__ で image を読み替えられるので、ここでは自前で上書きする
        super().__init__(pos, angle, speed)
        try:
            self.image = pygame.image.load("data/bullet_enemy_huge.png").convert_alpha()
            self.image = pygame.transform.scale(self.image, (40, 40))
        except (pygame.error, FileNotFoundError):
            # 大きくて目立つダミー Surface
            self.image = pygame.Surface((35, 35))
            self.image.fill((100, 0, 255))
        self.rect = self.image.get_rect(center=pos)
        # dx/dy は親クラスで設定済み





class Player(pygame.sprite.Sprite):
    """
    自機クラス
    """
    def __init__(self):
        super().__init__()
        try:
            # ダミー画像
            self.image = pygame.image.load("data/player.png").convert_alpha()
            self.image = pygame.transform.scale(self.image, (50, 50))  # サイズ調整
        except (pygame.error, FileNotFoundError):
            self.image = pygame.Surface((30, 40))
            self.image.fill((0, 128, 255))
        
        self.rect = self.image.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 50))
        
        # 当たり判定 (イラストより大幅に小さく)
        self.hitbox = pygame.Rect(0, 0, 8, 8)
        self.hitbox.center = self.rect.center

        # GRAZE判定 (hitboxより大きく、イラストより少し小さい)
        self.grazebox = self.rect.inflate(-10, -10) 

        self.speed = 5
        self.lives = 10
        self.shoot_delay = 100  # ホーミング弾の発射間隔 (ms)
        self.last_shot = pygame.time.get_ticks()

        # 復活関連
        self.is_respawning = False
        self.respawn_timer = 0
        self.respawn_duration = 10000  # 10秒
        self.blink_timer = 0
        self.is_visible = True

    def update(self, keys: pygame.key.ScancodeWrapper, bullets_group: pygame.sprite.Group, target_boss: pygame.sprite.Sprite):
        """
        プレイヤーの更新
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

        current_speed = self.speed 

        # 低速（スピードダウン）機能は別グループ課題で導入される可能性がありますが
        # 今回はそのまま current_speed を使います（他チームの変更に影響されないよう）。
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
        self.image.set_alpha(255)  # 点滅終了
        self.rect.center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 50)
        self.hitbox.center = self.rect.center
        self.grazebox.center = self.rect.center


class Boss(pygame.sprite.Sprite):
    """
    ボスクラス - EXステージ対応を追加
    """
    def __init__(self):
        super().__init__()
        try:
            # 通常ボス画像
            self.normal_image = pygame.image.load("data/boss.png").convert_alpha()
            self.normal_image = pygame.transform.scale(self.normal_image, (150, 150))
        except (pygame.error, FileNotFoundError):
            self.normal_image = pygame.Surface((100, 100))
            self.normal_image.fill((255, 0, 128))

        # ★EX用ボス画像（存在すれば差し替え）
        try:
            # ★EX用画像がある場合はこちらを用意してください:
            # data/boss_ex.png を用意するとEXステージで差し替えます。
            self.ex_image = pygame.image.load("data/boss_ex.png").convert_alpha()
            self.ex_image = pygame.transform.scale(self.ex_image, (150, 150))
        except (pygame.error, FileNotFoundError):
            # EX用画像がなければ通常画像を代用（コメント行で分かりやすくしています）
            # --- ここに EX 用ボス画像を配置してください (data/boss_ex.png) ---
            self.ex_image = self.normal_image

        # 初期は通常画像
        self.image = self.normal_image
        self.rect = self.image.get_rect(center=(SCREEN_WIDTH // 2, 150))

        # (名前, HP, 弾幕パターンメソッド)
        self.skill = [
            ("STAGE1", 100, self.skill_pattern_1),
            ("STAGE2", 150, self.skill_pattern_2),
            ("STAGE3", 200, self.skill_pattern_3),
        ]
        
        # EX用スペル（後で start_ex_stage で設定する）
        self.ex_skill = [
            # name, hp, pattern placeholder (hpは合計で設定する)
            ("EX STAGE", 0, self.ex_pattern_final),
        ]

        self.is_ex_stage = False  # EX判定フラグ
        
        self.current_skill_index = -1
        self.hp = 0
        self.skill_start_time = 0
        self.clear_times = []
        self.is_active = False
        self.pattern_timer = 0
        
        # ランダム移動用の変数
        self.move_timer = 0
        self.move_target_pos = self.rect.center
        self.move_speed = 2  # ボスの移動速度

        self.next_skill()  # 最初のスペルカードを開始

    def start_ex_stage(self):
        """
        EXステージを開始する（HP とパターンを EX に変更、画像差し替え）
        仕様:
         1. 敵のHPは通常ステージ(1~3)の合計
         2. 攻撃は今までのパターンを扱う（+ 特大弾パターンを追加）
         3. 別画像を使用
         4. ボムは使用不可（未実装） -> このフラグはコメントで示す
        """
        # 合計HPを計算して ex_skill に代入
        total_hp = sum(card[1] for card in self.skill)
        self.ex_skill[0] = (self.ex_skill[0][0], total_hp, self.ex_skill[0][2])

        # 切り替え
        self.is_ex_stage = True
        self.image = self.ex_image  # ★EX用画像に差し替え（用意しておいてください）
        self.rect = self.image.get_rect(center=(SCREEN_WIDTH // 2, 150))

        # EX 用の skill リストに切り替え
        self.skill = self.ex_skill
        self.current_skill_index = -1
        self.clear_times = []
        self.is_active = True
        self.next_skill()

        # NOTE: ボム無効化は別機能側の実装が必要。ここでは「ボムは使えない」ことを仕様コメントで示します。
        # （実装例: player.has_bomb フラグを参照して main 側で使用不可にする等）

    def next_skill(self):
        """
        次のスキル（スペル）に移行する
        """
        self.current_skill_index += 1
        if self.current_skill_index < len(self.skill):
            name, max_hp, pattern_func = self.skill[self.current_skill_index]
            self.hp = max_hp
            self.skill_start_time = pygame.time.get_ticks()
            self.current_pattern = pattern_func
            self.is_active = True
            self.pattern_timer = 0  # パターンタイマーリセット
        else:
            # ボス撃破
            self.is_active = False
            # 通常ステージ時は消去するが、EXステージ時は演出・リザルトのため消去しない
            if not self.is_ex_stage:
                self.kill()

    def update(self, bullets_group: pygame.sprite.Group, player_pos: tuple[int, int]):
        if not self.is_active:
            return

        self.pattern_timer += 1
        
        # ボスのランダム移動処理
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

        # スキル実行（現在のパターン関数を呼ぶ）
        # pattern 関数のシグネチャは (bullets_group, player_pos)
        self.current_pattern(bullets_group, player_pos)

    def check_skill_transition(self) -> bool:
        """
        ステージ移行条件 (HPゼロのみ) をチェック
        """
        if not self.is_active:
            return False

        if self.hp <= 0:
            # クリアタイムを記録
            elapsed_time_ms = pygame.time.get_ticks() - self.skill_start_time
            self.clear_times.append(elapsed_time_ms / 1000.0)  # 秒に変換してリストに追加

            self.next_skill()
            return True
        return False

    def hit(self, damage: int):
        if self.is_active:
            self.hp -= damage

    # UI用ゲッター
    def get_current_skill_name(self) -> str:
        if 0 <= self.current_skill_index < len(self.skill):
            return self.skill[self.current_skill_index][0]
        return ""

    def get_current_skill_max_hp(self) -> int:
        if 0 <= self.current_skill_index < len(self.skill):
            return self.skill[self.current_skill_index][1]
        return 1

    def get_current_elapsed_time(self) -> float:
        """ 経過時間を返す """
        if self.is_active:
            return (pygame.time.get_ticks() - self.skill_start_time) / 1000.0
        return 0.0

    # ========== 既存のパターン ==========
    def skill_pattern_1(self, bullets_group: pygame.sprite.Group, player_pos: tuple[int, int]):
        """
        ステージ1: 小弾 (小弾と大弾の全方位弾)
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

    def skill_pattern_2(self, bullets_group: pygame.sprite.Group, player_pos: tuple[int, int]):
        """
        ステージ2: レーザー (細レーザーと置きレーザー)
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

    def skill_pattern_3(self, bullets_group: pygame.sprite.Group, player_pos: tuple[int, int]):
        """
        ステージ3: 複合弾幕 (全種類使用)
        """
        if self.pattern_timer % 70 == 0:
            density = 6
            for i in range(density):
                angle = (360 / density) * i - (self.pattern_timer / 20) + random.uniform(-5, 5)
                bullets_group.add(EnemyLargeBullet(self.rect.center, angle, 2))
        
        if self.pattern_timer % 25 == 0:
            angle_to_player = math.degrees(math.atan2(player_pos[1] - self.rect.centery, player_pos[0] - self.rect.centerx))
            bullets_group.add(EnemyBullet(self.rect.center, angle_to_player + random.uniform(-10, 10), 4))
            
        if self.pattern_timer % 50 == 0:
            x = random.randint(50, SCREEN_WIDTH - 50)
            y = random.randint(SCREEN_HEIGHT // 2, SCREEN_HEIGHT - 50)
            bullets_group.add(EnemyDelayedLaser((x, y), delay=30, duration=30))

    # ========== EX 用最終パターン（既存パターン＋特大弾） ==========
    def ex_pattern_final(self, bullets_group: pygame.sprite.Group, player_pos: tuple[int, int]):
        """
        EXステージ最終パターン:
        - 既存の全パターンを高頻度で組み合わせる
        - さらに特大弾 (EnemyHugeBullet) を追加で発射する
        """
        # 全方位（強化）
        if self.pattern_timer % 40 == 0:
            density = 10
            for i in range(density):
                angle = (360 / density) * i + (self.pattern_timer / 5) + random.uniform(-8, 8)
                speed = 3
                bullets_group.add(EnemyLargeBullet(self.rect.center, angle, speed))

        # 自機狙い小弾（強化）
        if self.pattern_timer % 8 == 0:
            spread = 15
            angle_to_player = math.degrees(math.atan2(player_pos[1] - self.rect.centery,
                                                      player_pos[0] - self.rect.centerx))
            for i in range(-1, 2):
                angle = angle_to_player + (i * spread) + random.uniform(-6, 6)
                speed = 5
                bullets_group.add(EnemyBullet(self.rect.center, angle, speed))

        # 細レーザー（高頻度）
        if self.pattern_timer % 15 == 0:
            angle_to_player = math.degrees(math.atan2(player_pos[1] - self.rect.centery,
                                                      player_pos[0] - self.rect.centerx))
            bullets_group.add(EnemyLaser(self.rect.center, angle_to_player + random.uniform(-10, 10), 9))

        # 置きレーザー（短めの遅延・頻度高め）
        if self.pattern_timer % 30 == 0:
            x = random.randint(50, SCREEN_WIDTH - 50)
            y = random.randint(SCREEN_HEIGHT // 3, SCREEN_HEIGHT - 50)
            bullets_group.add(EnemyDelayedLaser((x, y), delay=20, duration=40))

        # 特大弾（円形に展開するもの）
        if self.pattern_timer % 150 == 0:
            count = 4
            for i in range(count):
                angle = (360 / count) * i + self.pattern_timer
                speed = 1.5
                bullets_group.add(EnemyHugeBullet(self.rect.center, angle, speed))

        # 特大弾（自機狙いでゆっくり発射）
        if self.pattern_timer % 90 == 0:
            angle_to_player = math.degrees(math.atan2(player_pos[1] - self.rect.centery,
                                                      player_pos[0] - self.rect.centerx))
            bullets_group.add(EnemyHugeBullet(self.rect.center, angle_to_player + random.uniform(-5, 5), 2.5))





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
    if getattr(boss, "is_active", False):
        # スペルカード名
        skill_name = boss.get_current_skill_name()
        skill_text = font.render(skill_name, True, WHITE)
        screen.blit(skill_text, (SCREEN_WIDTH // 2 - skill_text.get_width() // 2, 10))

        # HPバー（EX中は色を変える）
        hp_ratio = boss.hp / boss.get_current_skill_max_hp() if boss.get_current_skill_max_hp() > 0 else 0
        hp_bar_width = max(0, (SCREEN_WIDTH - 40) * hp_ratio)
        pygame.draw.rect(screen, (100, 100, 100), (20, 40, SCREEN_WIDTH - 40, 20))
        hp_color = (255, 0, 255) if getattr(boss, "is_ex_stage", False) else (255, 0, 0)
        pygame.draw.rect(screen, hp_color, (20, 40, hp_bar_width, 20))

        # 経過時間
        elapsed_time = boss.get_current_elapsed_time()
        time_text = font.render(f"Time: {elapsed_time:.2f}", True, WHITE)  # 小数点以下2桁
        screen.blit(time_text, (SCREEN_WIDTH - time_text.get_width() - 10, 10))

def draw_game_over(screen: pygame.Surface):
    """ ゲームオーバー画面描画 """
    screen.fill(BLACK)
    font = pygame.font.Font(None, 74)
    text = font.render("GAME OVER", True, WHITE)
    screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, SCREEN_HEIGHT // 2 - 50))
    font = pygame.font.Font(None, 40)
    text = font.render("Press SPACE to Exit", True, WHITE)
    screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, SCREEN_HEIGHT // 2 + 20))
    pygame.display.flip()

def draw_results(screen: pygame.Surface, times: list[float]):
    """ リザルト画面描画（ここで CTRL 押下で EX へ行ける） """
    screen.fill(BLACK)
    font_large = pygame.font.Font(None, 74)
    font_medium = pygame.font.Font(None, 40)
    
    title = font_large.render("Clear!", True, (255, 255, 0))
    screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 80))

    total_time = 0.0
    y_offset = 200
    
    for i, time in enumerate(times):
        text = font_medium.render(f"Skill {i+1}: {time:.2f} sec", True, WHITE)
        screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, y_offset))
        y_offset += 40
        total_time += time

    y_offset += 20  # 少し間隔をあける
    pygame.draw.line(screen, WHITE, (100, y_offset), (SCREEN_WIDTH - 100, y_offset), 2)
    y_offset += 20

    total_text = font_medium.render(f"Total: {total_time:.2f} sec", True, WHITE)
    screen.blit(total_text, (SCREEN_WIDTH // 2 - total_text.get_width() // 2, y_offset))

    y_offset += 100
    # ここで CTRL キーを押すと EX ステージへ遷移します
    continue_text = font_medium.render("Press SPACE to Exit / CTRL for EX Stage", True, WHITE)
    screen.blit(continue_text, (SCREEN_WIDTH // 2 - continue_text.get_width() // 2, y_offset))
    
    pygame.display.flip()

# EX 関連の描画（演出）
def draw_ex_transition(screen: pygame.Surface, title: str, color: tuple[int, int, int]):
    """
    EXステージ突入 / クリア / 敗北 演出表示
    画像を使いたい場合は下記のコメント箇所に画像を配置してください。
    """
    screen.fill(BLACK)
    font_large = pygame.font.Font(None, 74)
    font_medium = pygame.font.Font(None, 40)
    
    title_text = font_large.render(title, True, color)
    screen.blit(title_text, (SCREEN_WIDTH // 2 - title_text.get_width() // 2, SCREEN_HEIGHT // 2 - 50))

    # ★画像を表示したい場合はここで blit してください:
    # 例:
    # try:
    #     ex_banner = pygame.image.load("data/ex_banner.png").convert_alpha()
    #     ex_banner = pygame.transform.scale(ex_banner, (400, 200))
    #     screen.blit(ex_banner, (SCREEN_WIDTH//2 - 200, SCREEN_HEIGHT//2 + 10))
    # except (pygame.error, FileNotFoundError):
    #     pass

    msg = ""
    if title == "EXTRA STAGE START":
        msg = "Prepare for the ultimate challenge!"
    elif title == "EX STAGE CLEAR":
        msg = "The nightmare is over."
    elif title == "EX STAGE FAILED":
        msg = "Retreat and Try Again."
    else:
        msg = "..."

    msg_text = font_medium.render(msg, True, WHITE)
    screen.blit(msg_text, (SCREEN_WIDTH // 2 - msg_text.get_width() // 2, SCREEN_HEIGHT // 2 + 30))
    
    pygame.display.flip()

def draw_ex_results(screen: pygame.Surface, time: float):
    """ EXステージのクリアタイムを表示するリザルト """
    screen.fill(BLACK)
    font_large = pygame.font.Font(None, 74)
    font_medium = pygame.font.Font(None, 40)
    
    title = font_large.render("EX STAGE COMPLETE", True, (0, 255, 255)) 
    screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 80))

    y_offset = 200
    
    # クリアタイムの表示
    text = font_medium.render(f"EX Time: {time:.2f} sec", True, (255, 255, 0))
    screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, y_offset))
    
    y_offset += 100
    continue_text = font_medium.render("Press SPACE to Exit", True, WHITE)
    screen.blit(continue_text, (SCREEN_WIDTH // 2 - continue_text.get_width() // 2, y_offset))
    
    pygame.display.flip()

def main():
    """
    ゲームのメイン関数
    """
    pygame.init()
    # mixer 初期化は環境によって失敗する可能性があるため try/except 推奨
    try:
        pygame.mixer.init()
    except pygame.error:
        # サウンドが使えない環境でも動作するようにする
        pass

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("某弾幕シューティング風ボスステージ (EX Stage 追加)")
    clock = pygame.time.Clock()

    # サウンドの読み込み (資料)
    try:
        # BGM の読み込みと再生 (無限ループ)
        pygame.mixer.music.load("data/bgm.mp3")
        pygame.mixer.music.play(loops=-1) #

        # 効果音の読み込み
        se_hit = pygame.mixer.Sound("data/se_hit.wav") #
        se_graze = pygame.mixer.Sound("data/se_graze.wav")
    except (pygame.error, FileNotFoundError):
        se_hit = None
        se_graze = None

    # スプライトグループの作成
    all_sprites = pygame.sprite.Group()
    player_bullets = pygame.sprite.Group()
    enemy_bullets = pygame.sprite.Group()

    # インスタンスの作成
    player = Player()
    boss = Boss()
    all_sprites.add(player, boss)

    # ゲーム変数
    score = 0
    game_state = "playing"
    running = True

    # EX 関連タイマー
    transition_timer = 0
    transition_duration = 60  # フレーム数（1秒）

    # メインループ
    while running:
        
        # イベント処理
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            if game_state == "playing":
                # プレイヤー復活処理
                if player.is_respawning and event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        player.respawn()

            elif game_state == "results":
                # クリア画面での操作: SPACE で終了、CTRL で EX 突入
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        running = False
                    if event.key == pygame.K_LCTRL or event.key == pygame.K_RCTRL:
                        # EX 突入演出へ
                        game_state = "ex_transition"
                        transition_timer = 0
                        # EX 演出中はボスとプレイヤーを一旦 all_sprites から外しておく（見た目の演出）
                        try:
                            all_sprites.remove(boss)
                            all_sprites.remove(player)
                        except ValueError:
                            pass

            elif game_state == "game_over" or game_state == "ex_results":
                # ゲームオーバー/EXリザルト画面でSPACEキーを押したら終了
                if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                    running = False

            elif game_state == "ex_playing":
                # プレイヤー復活（EX 中も SPACE で復活可能）
                if player.is_respawning and event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        player.respawn()


        # 状態ごとの更新・描画処理

        if game_state == "playing":
            # 更新処理
            
            keys = pygame.key.get_pressed()
            
            player.update(keys, player_bullets, boss)

            # boss が非アクティブになっている場合、update を呼ばない（例：既に倒された）
            if boss.is_active:
                boss.update(enemy_bullets, player.rect.center)
            player_bullets.update()
            
            # 敵弾の更新 (画面外に出た弾を消去し、スコア加算)
            avoided_bullets_score = 0
            for bullet in list(enemy_bullets):
                bullet.update()
                if not screen.get_rect().colliderect(bullet.rect):
                    bullet.kill()
                    # 弾を1つ避けきったらスコア1UP
                    avoided_bullets_score += 1
            score += avoided_bullets_score

            # 当たり判定

            # 自機弾 vs ボス
            if boss.is_active:
                hits = pygame.sprite.spritecollide(boss, player_bullets, True)
                if hits:
                    # 1ダメージ = 1ヒットとして処理
                    damage = len(hits)
                    boss.hit(damage)
                    # 1ダメージにつきスコア1UP
                    score += damage

            # 敵弾 vs 自機 (被弾 & GRAZE)
            if not player.is_respawning:
                
                # GRAZE (かすり) 判定
                graze_list = pygame.sprite.spritecollide(player, enemy_bullets, False, pygame.sprite.collide_rect)
                
                for bullet in graze_list:
                    # 置きレーザーが 'warning' 状態なら判定しない
                    if isinstance(bullet, EnemyDelayedLaser) and bullet.state != "active":
                        continue

                    if not bullet.grazed:
                        if not player.hitbox.colliderect(bullet.rect):
                            score += 20 # GRAZEスコア20
                            bullet.grazed = True
                            if se_graze:
                                se_graze.play()

                # 被弾判定 (hitbox)
                hit_bullets = []
                for bullet in list(enemy_bullets):
                    # 置きレーザーが 'warning' 状態なら判定しない
                    if isinstance(bullet, EnemyDelayedLaser) and bullet.state != "active":
                        continue

                    if player.hitbox.colliderect(bullet.rect):
                        hit_bullets.append(bullet)

                if hit_bullets:
                    if se_hit:
                        se_hit.play()
                    
                    player.hit()
                    
                    for bullet in list(enemy_bullets):
                        bullet.kill()
                    
                    if player.lives <= 0:
                        game_state = "game_over"

            # ステージ移行判定
            if boss.check_skill_transition():
                # 移行時に弾幕を消去
                for bullet in list(enemy_bullets):
                    bullet.kill()
                
                if not boss.is_active:
                    game_state = "results"  # リザルト画面に移行

            # 描画処理
            screen.fill(BLACK)
            
            all_sprites.draw(screen)
            player_bullets.draw(screen)
            enemy_bullets.draw(screen)

            # UIの描画
            draw_ui(screen, score, player.lives, boss)
            
            # 復活待機中の表示
            if player.is_respawning:
                font = pygame.font.Font(None, 40)
                text = font.render("Press SPACE to Respawn", True, WHITE)
                screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, SCREEN_HEIGHT // 2 + 100))

            pygame.display.flip()

        elif game_state == "results":
            # リザルト画面描画
            draw_results(screen, boss.clear_times)

        # =========================================================
        # EXステージ関連処理
        # =========================================================
        elif game_state == "ex_transition":
            # EX突入演出
            draw_ex_transition(screen, "EXTRA STAGE START", (0, 255, 255))
            transition_timer += 1
            if transition_timer > transition_duration:
                # EXステージ開始
                # 1) EX用に boss を設定（HP合算・パターン差し替え・画像差し替え）
                boss.start_ex_stage()

                # 2) プレイヤーを復活（無敵時間を与えるため respawn を使う）
                player.respawn()

                # 3) 既存の敵弾を全消去（演出と公平性のため）
                for b in list(enemy_bullets):
                    b.kill()

                # 4) all_sprites にボスとプレイヤーを戻す
                try:
                    all_sprites.add(player)
                    all_sprites.add(boss)
                except Exception:
                    pass

                # 5) EXプレイ開始
                game_state = "ex_playing"

        elif game_state == "ex_playing":
            # EX ステージ中の更新処理（基本的に通常の playing と同様。ただし難度は boss.ex_pattern_final が高い）
            keys = pygame.key.get_pressed()
            
            player.update(keys, player_bullets, boss)

            if boss.is_active:
                boss.update(enemy_bullets, player.rect.center)
            player_bullets.update()

            # 敵弾の更新（画面外は消去、スコアは付与しない仕様にする）
            for bullet in list(enemy_bullets):
                bullet.update()
                if not screen.get_rect().colliderect(bullet.rect):
                    bullet.kill()

            # 当たり判定（自機弾 vs ボス）
            if boss.is_active:
                hits = pygame.sprite.spritecollide(boss, player_bullets, True)
                if hits:
                    damage = len(hits)
                    boss.hit(damage)

            # 被弾判定（敵弾 vs 自機）
            if not player.is_respawning:
                graze_list = pygame.sprite.spritecollide(player, enemy_bullets, False, pygame.sprite.collide_rect)
                for bullet in graze_list:
                    if isinstance(bullet, EnemyDelayedLaser) and bullet.state != "active":
                        continue
                    if not bullet.grazed and player.grazebox.colliderect(bullet.rect) and not player.hitbox.colliderect(bullet.rect):
                        # EX中も GRAZE は有効（スコア処理はそのまま）
                        score += 20
                        bullet.grazed = True
                        if se_graze:
                            se_graze.play()

                # 被弾
                hit_bullets = []
                for bullet in list(enemy_bullets):
                    if isinstance(bullet, EnemyDelayedLaser) and bullet.state != "active":
                        continue
                    if player.hitbox.colliderect(bullet.rect):
                        hit_bullets.append(bullet)

                if hit_bullets:
                    if se_hit:
                        se_hit.play()
                    player.hit()
                    for bullet in list(enemy_bullets):
                        bullet.kill()
                    if player.lives <= 0:
                        # EX 敗北演出へ
                        game_state = "ex_fail_anim"
                        transition_timer = 0

            # スキル（スペル）移行判定
            if boss.check_skill_transition():
                # 移行時に弾を消去
                for b in list(enemy_bullets):
                    b.kill()
                if not boss.is_active:
                    # EX クリア（演出へ）
                    game_state = "ex_clear_anim"
                    transition_timer = 0

            # 描画
            screen.fill(BLACK)
            all_sprites.draw(screen)
            player_bullets.draw(screen)
            enemy_bullets.draw(screen)
            draw_ui(screen, score, player.lives, boss)

            if player.is_respawning:
                font = pygame.font.Font(None, 40)
                text = font.render("Press SPACE to Respawn", True, WHITE)
                screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, SCREEN_HEIGHT // 2 + 100))

            pygame.display.flip()

        elif game_state == "ex_clear_anim":
            # EX クリア演出
            draw_ex_transition(screen, "EX STAGE CLEAR", (255, 255, 0))
            transition_timer += 1
            if transition_timer > transition_duration * 2:
                game_state = "ex_results"

        elif game_state == "ex_fail_anim":
            # EX 敗北演出
            draw_ex_transition(screen, "EX STAGE FAILED", (255, 0, 0))
            transition_timer += 1
            if transition_timer > transition_duration * 2:
                # EX 敗北後は通常のゲームオーバー画面へ遷移
                game_state = "game_over"

        elif game_state == "ex_results":
            # EX リザルト画面（最新の clear time を表示）
            ex_clear_time = boss.clear_times[-1] if boss.clear_times else 0.0
            draw_ex_results(screen, ex_clear_time)

        elif game_state == "game_over":
            draw_game_over(screen)

        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()