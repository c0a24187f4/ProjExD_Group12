import pygame as pg
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


class PlayerBullet(pg.sprite.Sprite):
    """
    自機の弾 (ホーミング)
    """
    def __init__(self, pos: tuple[int, int], target: pg.sprite.Sprite):
        super().__init__()
        try:
            # (ダミー画像)
            self.image = pg.image.load("data/bullet_player.png").convert_alpha()
            self.image = pg.transform.scale(self.image, (12, 12))
        except pg.error:
            self.image = pg.Surface((10, 10))
            self.image.fill((0, 255, 255))
        
        self.rect = self.image.get_rect(center=pos)
        self.target = target
        self.speed = 8
        self.turn_speed = 3  # ホーミングの追尾性能 (角度)

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


class EnemyBullet(pg.sprite.Sprite):
    """
    敵の弾 (小弾)
    """
    def __init__(self, pos: tuple[int, int], angle: float, speed: float):
        super().__init__()
        try:
            # (ダミー画像)
            self.image = pg.image.load("data/bullet_enemy_small.png").convert_alpha()
            self.image = pg.transform.scale(self.image, (10, 10))
        except pg.error:
            self.image = pg.Surface((8, 8))
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
            self.image = pg.image.load("data/bullet_enemy_large.png").convert_alpha()
            self.image = pg.transform.scale(self.image, (25, 25))
        except pg.error:
            self.image = pg.Surface((20, 20))
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
            self.original_image = pg.image.load("data/laser.png").convert_alpha()
            self.original_image = pg.transform.scale(self.original_image, (100, 5))  # 細長い画像
        except pg.error:
            self.original_image = pg.Surface((100, 5))
            self.original_image.fill((255, 200, 0))
        
        # 角度に合わせて画像を回転
        self.image = pg.transform.rotate(self.original_image, -angle)
        self.rect = self.image.get_rect(center=pos)


class EnemyDelayedLaser(pg.sprite.Sprite):
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
            self.warn_image = pg.image.load("data/laser_warning.png").convert_alpha()
            self.warn_image = pg.transform.scale(self.warn_image, (30, 300))
        except pg.error:
            self.warn_image = pg.Surface((30, 300))
            self.warn_image.fill((100, 100, 0))
        
        # 警告画像を半透明にする
        self.warn_image.set_alpha(100) 

        try:
            # (ダミー画像) 本体
            self.active_image = pg.image.load("data/laser.png").convert_alpha()
            self.active_image = pg.transform.scale(self.active_image, (30, 300))
        except pg.error:
            self.active_image = pg.Surface((30, 300))
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


class Player(pg.sprite.Sprite):
    """
    自機クラス
    """
    def __init__(self):
        super().__init__()
        try:
            # ダミー画像
            self.image = pg.image.load("data/player.png").convert_alpha()
            self.image = pg.transform.scale(self.image, (50, 50))  # サイズ調整
        except pg.error:
            self.image = pg.Surface((30, 40))
            self.image.fill((0, 128, 255))
        
        self.rect = self.image.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 50))
        
        # 当たり判定 (イラストより大幅に小さく)
        self.hitbox = pg.Rect(0, 0, 8, 8)
        self.hitbox.center = self.rect.center

        # GRAZE判定 (hitboxより大きく、イラストより少し小さい)
        self.grazebox = self.rect.inflate(-10, -10) 

        self.speed = 5 
        self.lives = 10
        self.shoot_delay = 100  # ホーミング弾の発射間隔 (ms)
        self.last_shot = pg.time.get_ticks()

        # 復活関連
        self.is_respawning = False
        self.respawn_timer = 0
        self.respawn_duration = 10000  # 10秒
        self.blink_timer = 0
        self.is_visible = True

    def update(self, keys: pg.key.ScancodeWrapper, bullets_group: pg.sprite.Group, target_boss: pg.sprite.Sprite):
        """
        プレイヤーの更新
        """
        
        if self.is_respawning:
            # 復活待機中 (10秒タイマー)
            now = pg.time.get_ticks()
            if now - self.respawn_timer > self.respawn_duration:
                self.respawn()
            
            # 点滅処理 (無敵中は操作不可)
            self.blink_timer = (self.blink_timer + 1) % 20
            self.is_visible = self.blink_timer < 10
            self.image.set_alpha(255 if self.is_visible else 0)
            return

        current_speed = self.speed 
        if keys[pg.K_LSHIFT]:
            current_speed *=0.5

        if keys[pg.K_w]:
            self.rect.y -= current_speed
        if keys[pg.K_s]:
            self.rect.y += current_speed
        if keys[pg.K_a]:
            self.rect.x -= current_speed
        if keys[pg.K_d]:
            self.rect.x += current_speed

        # 画面端の制限
        self.rect.clamp_ip(pg.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))
        
        # hitboxとgrazeboxを本体に追従させる
        self.hitbox.center = self.rect.center
        self.grazebox.center = self.rect.center

        # 射撃 (ホーミング)
        self.shoot(bullets_group, target_boss)

    def shoot(self, bullets_group: pg.sprite.Group, target_boss: pg.sprite.Sprite):
        """
        ホーミング弾を発射する
        """
        now = pg.time.get_ticks()
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
            self.respawn_timer = pg.time.get_ticks()
            
    def respawn(self):
        """
        復活処理 (SPACEキーまたはタイマー)
        """
        self.is_respawning = False
        self.image.set_alpha(255)  # 点滅終了
        self.rect.center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 50)
        self.hitbox.center = self.rect.center
        self.grazebox.center = self.rect.center


class Boss(pg.sprite.Sprite):
    """
    ボスクラス
    """
    def __init__(self):
        super().__init__()
        try:
            # ダミー画像
            self.image = pg.image.load("data/boss.png").convert_alpha()
            self.image = pg.transform.scale(self.image, (150, 150))
        except pg.error:
            self.image = pg.Surface((100, 100))
            self.image.fill((255, 0, 128))
            
        self.rect = self.image.get_rect(center=(SCREEN_WIDTH // 2, 150))

        # (名前, HP, 弾幕パターンメソッド)
        self.skill = [
            ("ステージ1「通常弾幕」", 100, self.skill_pattern_1),
            ("ステージ2「レーザー弾幕」", 150, self.skill_pattern_2),
            ("ステージ3「全弾幕」", 200, self.skill_pattern_3),
        ]
        
        self.current_skill_index = -1
        self.hp = 0
        self.skill_start_time = 0
        self.clear_times = []
        self.is_active = False
        self.pattern_timer = 0
        
        # ランダム移動用の変数を追加
        self.move_timer = 0
        self.move_target_pos = self.rect.center
        self.move_speed = 2  # ボスの移動速度

        self.next_skill()  # 最初のスペルカードを開始

    def next_skill(self):
        """
        次のスペルカードに移行する
        """
        self.current_skill_index += 1
        if self.current_skill_index < len(self.skill):
            name, max_hp, pattern_func = self.skill[self.current_skill_index]
            self.hp = max_hp
            self.skill_start_time = pg.time.get_ticks()
            self.current_pattern = pattern_func
            self.is_active = True
            self.pattern_timer = 0  # パターンタイマーリセット
        else:
            # ボス撃破
            self.is_active = False
            self.kill()  # ボスを消去

    def update(self, bullets_group: pg.sprite.Group, player_pos: tuple[int, int]):
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
        # ===================================

        # スキル実行
        self.current_pattern(bullets_group, player_pos)

    def check_skill_transition(self) -> bool:
        """
        ステージ移行条件 (HPゼロのみ) をチェック
        """
        if not self.is_active:
            return False

        if self.hp <= 0:
            
            # クリアタイムを記録
            elapsed_time_ms = pg.time.get_ticks() - self.skill_start_time
            self.clear_times.append(elapsed_time_ms / 1000.0)  # 秒に変換してリストに追加

            self.next_skill()
            return True
        return False

    def hit(self, damage: int):
        if self.is_active:
            self.hp -= damage

    # UI用ゲッター
    def get_current_skill_name(self) -> str:
        if self.is_active:
            return self.skill[self.current_skill_index][0]
        return ""

    def get_current_skill_max_hp(self) -> int:
        if self.is_active:
            return self.skill[self.current_skill_index][1]
        return 1

    def get_current_elapsed_time(self) -> float:
        """ 経過時間を返す """
        if self.is_active:
            return (pg.time.get_ticks() - self.skill_start_time) / 1000.0
        return 0.0

    def skill_pattern_1(self, bullets_group: pg.sprite.Group, player_pos: tuple[int, int]):
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

    def skill_pattern_2(self, bullets_group: pg.sprite.Group, player_pos: tuple[int, int]):
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

    def skill_pattern_3(self, bullets_group: pg.sprite.Group, player_pos: tuple[int, int]):
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


def draw_ui(screen: pg.Surface, score: int, lives: int, boss: Boss):
    """
    UI（スコア、残機、ボスHPなど）を描画する
    """
    font = pg.font.Font(None, 36)
    
    # スコア
    score_text = font.render(f"Score: {score}", True, WHITE)
    screen.blit(score_text, (10, 10))
    
    # 残機
    lives_text = font.render(f"Lives: {lives}", True, WHITE)
    screen.blit(lives_text, (10, 40))

    # ボスHP
    if boss.is_active:
        # スペルカード名
        skill_name = boss.get_current_skill_name()
        skill_text = font.render(skill_name, True, WHITE)
        screen.blit(skill_text, (SCREEN_WIDTH // 2 - skill_text.get_width() // 2, 10))

        # HPバー
        hp_ratio = boss.hp / boss.get_current_skill_max_hp()
        hp_bar_width = (SCREEN_WIDTH - 40) * hp_ratio
        pg.draw.rect(screen, (100, 100, 100), (20, 40, SCREEN_WIDTH - 40, 20))
        pg.draw.rect(screen, (255, 0, 0), (20, 40, hp_bar_width, 20))

        # 経過時間
        elapsed_time = boss.get_current_elapsed_time()
        time_text = font.render(f"Time: {elapsed_time:.2f}", True, WHITE)  # 小数点以下2桁
        screen.blit(time_text, (SCREEN_WIDTH - time_text.get_width() - 10, 10))

def draw_game_over(screen: pg.Surface):
    """ ゲームオーバー画面描画 """
    screen.fill(BLACK)
    font = pg.font.Font(None, 74)
    text = font.render("GAME OVER", True, WHITE)
    screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, SCREEN_HEIGHT // 2 - 50))
    font = pg.font.Font(None, 40)
    text = font.render("Press SPACE to Exit", True, WHITE)
    screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, SCREEN_HEIGHT // 2 + 20))
    pg.display.flip()

def draw_results(screen: pg.Surface, times: list[float]):
    """ リザルト画面描画 """
    screen.fill(BLACK)
    font_large = pg.font.Font(None, 74)
    font_medium = pg.font.Font(None, 40)
    
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
    pg.draw.line(screen, WHITE, (100, y_offset), (SCREEN_WIDTH - 100, y_offset), 2)
    y_offset += 20

    total_text = font_medium.render(f"Total: {total_time:.2f} sec", True, WHITE)
    screen.blit(total_text, (SCREEN_WIDTH // 2 - total_text.get_width() // 2, y_offset))

    y_offset += 100
    continue_text = font_medium.render("Press SPACE to Exit", True, WHITE)
    screen.blit(continue_text, (SCREEN_WIDTH // 2 - continue_text.get_width() // 2, y_offset))
    
    pg.display.flip()


def main():
    """
    ゲームのメイン関数
    """
    pg.init()
    pg.mixer.init()

    screen = pg.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pg.display.set_caption("某弾幕シューティング風ボスステージ")
    clock = pg.time.Clock()

    #背景の追加した
    try:
        background_image = pg.image.load("data/HAIKEI.png").convert()
        # 画面サイズに合わせて背景画像をスケール (必要に応じて)
        # self.imageはSpriteの属性なので、ここでは直接screenに描画する
        background_image = pg.transform.scale(background_image, (SCREEN_WIDTH, SCREEN_HEIGHT))
    except pg.error as e:
        print(f"背景画像 'HAIKEI.png' の読み込みに失敗しました: {e}")
        # 失敗した場合、黒い背景を使用
        background_image = None

    #  サウンドの読み込み (資料)

    # BGMの読み込みと再生 (無限ループ)
    pg.mixer.music.load("data/BGM1.mp3")
    pg.mixer.music.play(loops=-1)

    # スプライトグループの作成
    all_sprites = pg.sprite.Group()
    player_bullets = pg.sprite.Group()
    enemy_bullets = pg.sprite.Group()

    # インスタンスの作成
    player = Player()
    boss = Boss()
    all_sprites.add(player, boss)

    # ゲーム変数
    score = 0
    game_state = "playing"
    running = True

    # メインループ
    while running:
        
        # イベント処理
        for event in pg.event.get():
            if event.type == pg.QUIT:
                running = False
            
            if game_state == "playing":
                # プレイヤー復活処理
                if player.is_respawning and event.type == pg.KEYDOWN:
                    if event.key == pg.K_SPACE:
                        player.respawn()

            elif game_state == "game_over":
                # ゲームオーバー画面でSPACEキーを押したら終了
                if event.type == pg.KEYDOWN:
                    if event.key == pg.K_SPACE:
                        running = False

            elif game_state == "results":
                # リザルト画面でSPACEキーを押したら終了
                if event.type == pg.KEYDOWN:
                    if event.key == pg.K_SPACE:
                        running = False

        # 状態ごとの更新・描画処理

        if game_state == "playing":
            # 更新処理
            
            keys = pg.key.get_pressed()
            
            player.update(keys, player_bullets, boss)

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

            # 当たり判定

            # 自機弾 vs ボス
            hits = pg.sprite.spritecollide(boss, player_bullets, True)
            if hits:
                # 1ダメージ = 1ヒットとして処理
                damage = len(hits)
                boss.hit(damage)
                # 1ダメージにつきスコア1UP
                score += damage

            # 敵弾 vs 自機 (被弾 & GRAZE)
            if not player.is_respawning:
                
                # GRAZE (かすり) 判定
                graze_list = pg.sprite.spritecollide(player, enemy_bullets, False, pg.sprite.collide_rect)
                
                for bullet in graze_list:
                    # 置きレーザーが 'warning' 状態なら判定しない
                    if isinstance(bullet, EnemyDelayedLaser) and bullet.state != "active":
                        continue

                    if not bullet.grazed:
                        if not player.hitbox.colliderect(bullet.rect):
                            score += 20 # GRAZEスコア20
                            bullet.grazed = True
                            #if se_graze:
                                #dse_graze.play()

                # 被弾判定 (hitbox)
                hit_bullets = []
                for bullet in enemy_bullets:
                    # 置きレーザーが 'warning' 状態なら判定しない
                    if isinstance(bullet, EnemyDelayedLaser) and bullet.state != "active":
                        continue

                    if player.hitbox.colliderect(bullet.rect):
                        hit_bullets.append(bullet)

                if hit_bullets:
                    #if se_hit:
                        #se_hit.play()
                    
                    player.hit()
                    
                    for bullet in enemy_bullets:
                        bullet.kill()
                    
                    if player.lives <= 0:
                        game_state = "game_over"

            # ステージ移行判定
            if boss.check_skill_transition():
                # 移行時に弾幕を消去
                for bullet in enemy_bullets:
                    bullet.kill()
                
                if not boss.is_active:
                    game_state = "results"  # リザルト画面に移行

            # 描画処理
            if background_image:
                screen.blit(background_image, (0, 0)) # 背景画像を描画
            else:
                screen.fill(BLACK) # 背景画像がなければ黒で塗りつぶす
            
            all_sprites.draw(screen)
            player_bullets.draw(screen)
            enemy_bullets.draw(screen)

            # UIの描画
            draw_ui(screen, score, player.lives, boss)
            
            # 復活待機中の表示
            if player.is_respawning:
                font = pg.font.Font(None, 40)
                text = font.render("Press SPACE to Respawn", True, WHITE)
                screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, SCREEN_HEIGHT // 2 + 100))

            pg.display.flip()

        elif game_state == "game_over":
            # ゲームオーバー画面描画 ---
            draw_game_over(screen)

        elif game_state == "results":
            # リザルト画面描画
            draw_results(screen, boss.clear_times)

        clock.tick(FPS)

    pg.quit()
    sys.exit()


if __name__ == "__main__":
    main()