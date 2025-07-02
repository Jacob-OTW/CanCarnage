import sys
import time
import pygame
import pymunk
import pymunk.pygame_util
import random
import math

from pymunk.examples.platformer import width

pygame.init()
screen = pygame.display.set_mode((1000, 700))

class Condition:
    def __init__(self, callback, text_cb):
        self.callback = callback
        self.text_cb = text_cb

    def check(self, can_list: list):
        return bool(self.callback(can_list))

class Level:
    def __init__(self, cans, build_time, ammo, builder_conditions, shooter_conditions, visual_aid_markers=None):
        self.cans = cans
        self.builder_time = build_time
        self.shooter_ammo = ammo
        self.builder_condition_cb = None
        self.shooter_score_cb = None

        self.builder_conditions = builder_conditions
        self.shooter_conditions = shooter_conditions
        self.visual_aid_markers = [] if visual_aid_markers is None else visual_aid_markers


class GameSingleton:
    def __init__(self, space, slingshot):
        self.space = space
        self.slingshot = slingshot

        self.builder_mode_enabled = True
        self.builder_mode_timer = None
        self.builder_mode_max_time = 20 # In seconds

        self.shooter_mode_enabled = False
        self.max_ammo = 0
        self.shooter_ammo = 0

        self.active_level: Level | None = None
        self.level_queue = []
        self.can_list = []


    def update(self, slingshot):
        if self.builder_mode_enabled and self.builder_mode_timer is not None:
            if time.time() - self.builder_mode_timer >= self.builder_mode_max_time:
                self.builder_mode_enabled = False
                self.builder_mode_timer = None

                self.shooter_mode_enabled = True
                self.shooter_ammo = self.active_level.shooter_ammo

        if self.shooter_mode_enabled and self.shooter_ammo <= 0 and slingshot.dyn_bird is None:
            self.next_level()

    def build_timer_start(self):
        self.builder_mode_timer = time.time()

    def get_build_timer(self) -> float:
        if self.builder_mode_timer is None:
            return -1.0
        return self.builder_mode_max_time - (time.time() - self.builder_mode_timer)

    def use_ball(self) -> bool:
        if self.shooter_mode_enabled and self.shooter_ammo > 0:
            self.shooter_ammo -= 1
            return True
        return False

    def next_level(self):
        if len(self.level_queue) == 0:
            self.active_level = None
            return

        self.active_level = self.level_queue.pop(0)

        self.shooter_mode_enabled = False
        self.builder_mode_enabled = True
        self.builder_mode_timer = None

        self.max_ammo = self.active_level.shooter_ammo
        self.shooter_ammo = self.max_ammo
        self.builder_mode_max_time = self.active_level.builder_time

        for can_body, can_shape in self.can_list:
            can_body: pymunk.Body
            # Cursed way of doing it, needed it done fast
            can_body.__dict__["done_for"] = True
            self.space.remove(can_body, can_shape)

        self.can_list.clear()

        for ball_body, ball_shape in self.slingshot.dyn_bird_list:
            self.space.remove(ball_body, ball_shape)

        self.slingshot.dyn_bird_list.clear()

        for i in range(self.active_level.cans):
            can = spawn_can((screen.width / 2 + random.randint(-150, 150), screen.height / 2), self.space)
            self.can_list.append(can)

    def add_level(self, level):
        self.level_queue.append(level)
        if self.active_level is None:
            self.next_level()


class SlingShot:
    def __init__(self, anchor_pos, space: pymunk.Space):
        self.anchor_pos = anchor_pos

        self.max_draw_distance = 200

        # Bird settings
        bird_radius = 15
        self.bird_body = pymunk.Body(1, pymunk.moment_for_circle(1, 0, bird_radius), body_type=pymunk.Body.KINEMATIC)
        self.bird_body.position = anchor_pos
        self.bird_shape = pymunk.Circle(self.bird_body, bird_radius)
        self.bird_shape.elasticity = 0.8
        space.add(self.bird_body, self.bird_shape)

        self.dragging_bird = False

        self.dyn_bird: pymunk.Body | None = None

        self.dyn_bird_list = []

    def create_dyn_instance(self, space):
        self.dyn_bird = pymunk.Body()
        self.dyn_bird.position = self.bird_body.position

        dyn_circle = pymunk.Circle(self.dyn_bird, 15)
        dyn_circle.mass = 60
        dyn_circle.elasticity = 0.3
        dyn_circle.friction = 0.5

        self.dyn_bird_list.append((self.dyn_bird, dyn_circle))

        space.add(self.dyn_bird, dyn_circle)
        return self.dyn_bird

    def update(self, space):
        if self.dragging_bird:
            mouse = pygame.Vector2(pymunk.pygame_util.get_mouse_pos(screen)) - self.anchor_pos
            self.bird_body.position = tuple(mouse.clamp_magnitude(self.max_draw_distance).xy + self.anchor_pos)
        else:
            self.bird_body.position = self.anchor_pos

        if self.dyn_bird and (self.dyn_bird.velocity.length < 50 or self.dyn_bird.position.length >= 2000):
            self.dyn_bird = None
            space.add(self.bird_body, self.bird_shape)

class HelperHand(pygame.sprite.Sprite):
    def __init__(self, target: pymunk.Body, *groups, image="open_hand.png", offset_length=200, offset_angle=45):
        super().__init__(*groups)
        self.target: pymunk.Body = target

        self.image = pygame.image.load(f"assets/images/{image}")
        self.image.set_alpha(127)

        self.offset_length = offset_length
        self.offset_angle = offset_angle

        self.position = pygame.Vector2(pymunk.pygame_util.to_pygame(target.position, screen))
        self.rect = self.image.get_rect(center=self.position.xy)

        self.timer = time.time()

    def update(self, *args, **kwargs):
        sin_val = ((time.time() - self.timer) % 3.14) * (1 / 3.14)
        offset = pygame.Vector2(abs(sin_val / 2) * self.offset_length, 0).rotate(self.offset_angle)
        self.position = pygame.Vector2(pymunk.pygame_util.to_pygame(self.target.position + offset, screen)) + pygame.Vector2(12, 15)
        self.rect.center = self.position.xy

def spawn_can(pos, space) -> tuple[pymunk.Body, pymunk.Shape]:
    new_body = pymunk.Body()
    new_body.position = pos

    circle = pymunk.Poly.create_box(new_body, (31, 40))
    circle.mass = 20
    circle.elasticity = 0.2
    circle.friction = 1
    space.add(new_body, circle)
    return new_body, circle

def create_boundaries(space, width, height):
    rects = [
        [(192 + (789 / 2), 90), (789, 77)]
    ]

    for pos, size in rects:
        body = pymunk.Body(body_type=pymunk.Body.STATIC)
        body.position = pos
        shape = pymunk.Poly.create_box(body, size)
        shape.elasticity = 1
        shape.friction = 0.5
        space.add(body, shape)

def main():
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("arial", 22, pygame.font.Font.bold)

    ball_image = pygame.image.load("assets/images/ball.png")

    pymunk.pygame_util.positive_y_is_up = True
    space = pymunk.Space()
    space.gravity = 0, -981

    create_boundaries(space, screen.width, screen.height)

    slingshot = SlingShot(pymunk.Vec2d(*pymunk.pygame_util.from_pygame((227, 458), screen)), space)

    animation_group = pygame.sprite.Group()

    game = GameSingleton(space, slingshot)
    background_image = pygame.image.load("assets/images/background.png")
    clip_board_image = pygame.image.load("assets/images/clipboard.png")
    ball_icon_image = pygame.image.load("assets/images/ball.png")
    clock_image = pygame.image.load("assets/images/clock.png")

    options = pymunk.pygame_util.DrawOptions(screen)

    # Mouse dragging variables
    mouse_body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
    mouse_joint = None

    can_image = pygame.image.load("assets/images/can.png")

    level_0 = Level(6, 60, 3,
                    builder_conditions=[Condition(lambda c_list: sum(c[0].position.y < 150 for c in c_list) <= 3, lambda c_list: "Have at most 3x \n cans touching the floor")],
                    shooter_conditions=[Condition(lambda c_list: all(c[0].position.y < 0 for c in c_list), lambda c_list: "Shoot all cans off the table")]
                    )
    game.add_level(level_0)

    level_1 = Level(10, 90, 5,
                    builder_conditions=[Condition(lambda c_list: max(c[0].position.y for c in c_list) >= 260, lambda c_list: "Stack 4x cans on \n top of each other")],
                    shooter_conditions=[Condition(lambda c_list: sum(c[0].position.y < 0 for c in c_list) == 2, lambda c_list: "Leave 2x Cans on the table")]
                    )
    game.add_level(level_1)

    p2_hand = HelperHand(slingshot.bird_body, animation_group, image="open_hand_red.png", offset_angle=45 + 180)

    p1_hand = HelperHand(game.can_list[0][0], animation_group)

    while True:
        for event in pygame.event.get():
            match event.type:
                case pygame.QUIT:
                    return
                case pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        p = pymunk.Vec2d(*pymunk.pygame_util.to_pygame(event.pos, screen))
                        hit = space.point_query_nearest(p, 1, pymunk.ShapeFilter())
                        if hit and hit.shape.body == slingshot.bird_body and game.shooter_mode_enabled:
                            slingshot.dragging_bird = True
                        elif hit and hit.shape.body.body_type == pymunk.Body.DYNAMIC and game.builder_mode_enabled:
                            if game.builder_mode_timer is None:
                                game.build_timer_start()
                            dragged_body = hit.shape.body
                            mouse_joint = pymunk.PivotJoint(mouse_body, dragged_body, (0, 0),
                                                            dragged_body.world_to_local(p))
                            mouse_joint.max_force = 50000
                            mouse_joint.error_bias = (1 - 0.15) ** 60
                            space.add(mouse_joint)
                case pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        if slingshot.dragging_bird and game.shooter_mode_enabled:
                            slingshot.dragging_bird = False

                            dx = slingshot.anchor_pos[0] - slingshot.bird_body.position[0]
                            dy = slingshot.anchor_pos[1] - slingshot.bird_body.position[1]
                            impulse = (dx * 5, dy * 5)

                            if game.use_ball():
                                dyn_bird = slingshot.create_dyn_instance(space)

                                dyn_bird.velocity = impulse
                                space.remove(slingshot.bird_body, slingshot.bird_shape)
                        elif mouse_joint is not None:
                            space.remove(mouse_joint)
                            mouse_joint = None

        # Update mouse position
        mouse_pos = pymunk.pygame_util.get_mouse_pos(screen)
        mouse_body.position = mouse_pos

        slingshot.update(space)
        game.update(slingshot)
        animation_group.update()

        p1_hand.image.set_alpha(127 if game.builder_mode_enabled and game.builder_mode_timer is None and not hasattr(p1_hand.target, "done_for") else 0)
        p2_hand.image.set_alpha(127 if game.shooter_mode_enabled and game.shooter_ammo == game.max_ammo else 0)

        if game.active_level is not None:
            screen.blit(background_image, (0, 0))
            #space.debug_draw(options)

            screen.blit(clip_board_image, (screen.width - clip_board_image.width - 20, 20))

            for dyn_body, dyn_circle in slingshot.dyn_bird_list:
                dyn_body: pymunk.Body
                rotated_circle = pygame.transform.rotate(ball_image, math.degrees(dyn_body.angle))  # Radians to degrees
                rect = rotated_circle.get_rect(center=pymunk.pygame_util.to_pygame(dyn_body.position, screen))
                screen.blit(rotated_circle, rect.topleft)
            for can_body, can_shape in sorted(game.can_list, key=lambda c: c[0].position.y):
                can_body: pymunk.Body
                rotated_can = pygame.transform.rotate(can_image, math.degrees(can_body.angle))  # Radians to degrees
                rect = rotated_can.get_rect(center=pymunk.pygame_util.to_pygame(can_body.position, screen))
                screen.blit(rotated_can, rect.topleft)
            if slingshot.dyn_bird is None and game.shooter_mode_enabled:
                slingshot_circle = pygame.image.load("assets/images/ball.png")
                slingshot_circle.set_alpha(80)
                rect = slingshot_circle.get_rect(center=pymunk.pygame_util.to_pygame(slingshot.bird_body.position, screen))
                pygame.draw.line(screen, (0, 0, 0), (201, 453), pymunk.pygame_util.to_pygame(slingshot.bird_body.position, screen), 5)
                screen.blit(slingshot_circle, rect.topleft)
                pygame.draw.line(screen, (0, 0, 0), (245, 456), pymunk.pygame_util.to_pygame(slingshot.bird_body.position, screen), 5)

            animation_group.draw(screen)

            if game.builder_mode_enabled:
                pos = pygame.Vector2(35, 35)
                centre_offset = (pygame.Vector2(clock_image.size) / 2)
                screen.blit(clock_image, pos.xy)
                degree = 0 if game.builder_mode_timer is None else ((game.get_build_timer() / game.builder_mode_max_time) * 360)
                vec = pygame.Vector2(clock_image.width / 3, 0).rotate(-degree - 90)
                pygame.draw.line(screen, (90, 23, 26), pos + centre_offset, pos + centre_offset + vec, width=5)
            elif game.shooter_mode_enabled:
                for i in range(game.shooter_ammo):
                    screen.blit(ball_icon_image, (50 + 20 * i, 50))


            # Really shouldn't happen
            if game.active_level is not None:
                for i, condition in enumerate(game.active_level.builder_conditions if game.builder_mode_enabled else game.active_level.shooter_conditions):
                    font.set_strikethrough(condition.check(game.can_list))
                    screen.blit(font.render(condition.text_cb(game.can_list), True, (0, 0, 0)), (screen.width - clip_board_image.width, 130 + 50 * i))
        else:
            # Draw end-of-match score here
            screen.fill("Black")

        pygame.display.flip()
        clock.tick(50)
        space.step(1/50)


if __name__ == "__main__":
    sys.exit(main())