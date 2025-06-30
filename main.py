import sys
import time
import pygame
import pymunk
import pymunk.pygame_util
import random
import math

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
    def __init__(self):
        self.builder_mode_enabled = True
        self.builder_mode_timer = None
        self.builder_mode_max_time = 20 # In seconds

        self.shooter_mode_enabled = False
        self.max_ammo = 0
        self.shooter_ammo = 0

        self.active_level: Level | None = None
        self.level_queue = []


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
        else:
            self.active_level = self.level_queue.pop(0)

            self.shooter_mode_enabled = False
            self.builder_mode_enabled = True
            self.builder_mode_timer = None

            self.max_ammo = self.active_level.shooter_ammo
            self.shooter_ammo = self.max_ammo
            self.builder_mode_max_time = self.active_level.builder_time

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
    font = pygame.font.SysFont("arial", 32, pygame.font.Font.bold)

    ball_image = pygame.image.load("assets/images/ball.png")

    game = GameSingleton()
    background_image = pygame.image.load("assets/images/background.png")

    pymunk.pygame_util.positive_y_is_up = True
    space = pymunk.Space()
    space.gravity = 0, -981

    create_boundaries(space, screen.width, screen.height)

    slingshot = SlingShot(pymunk.Vec2d(*pymunk.pygame_util.from_pygame((227, 458), screen)), space)

    animation_group = pygame.sprite.Group()

    options = pymunk.pygame_util.DrawOptions(screen)
    space.debug_draw(options)

    # Mouse dragging variables
    mouse_body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
    mouse_joint = None

    can_list = []
    can_image = pygame.image.load("assets/images/can.png")

    level_0 = Level(1, 5, 1,
                    builder_conditions=[Condition(lambda c_list: sum(c[0].position.y < 150 for c in can_list) <= 10, lambda c_list: "Have at most 3x cans touching the floor")],
                    shooter_conditions=[Condition(lambda c_list: all(c[0].position.y < 0 for c in can_list), lambda c_list: "Shoot all cans off the table")]
                    )
    game.add_level(level_0)

    p2_hand = HelperHand(slingshot.bird_body, animation_group, image="open_hand_red.png", offset_angle=45 + 180)

    p1_hand = None
    for i in range(game.active_level.cans):
        can = spawn_can((screen.width / 2 + random.randint(-150, 150), screen.height / 2), space)
        can_list.append(can)
        if i == 0:
            p1_hand = HelperHand(can[0], animation_group)
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

        p1_hand.image.set_alpha(127 if game.builder_mode_enabled and game.builder_mode_timer is None else 0)
        p2_hand.image.set_alpha(127 if game.shooter_mode_enabled and game.shooter_ammo == game.max_ammo else 0)

        if len(game.level_queue) == 0 and game.active_level is not None:
            screen.blit(background_image, (0, 0))
            #space.debug_draw(options)

            for dyn_body, dyn_circle in slingshot.dyn_bird_list:
                dyn_body: pymunk.Body
                rotated_circle = pygame.transform.rotate(ball_image, math.degrees(dyn_body.angle))  # Radians to degrees
                rect = rotated_circle.get_rect(center=pymunk.pygame_util.to_pygame(dyn_body.position, screen))
                screen.blit(rotated_circle, rect.topleft)
            for can_body, can_shape in sorted(can_list, key=lambda c: c[0].position.y):
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
                screen.blit(font.render("Drag block to start timer" if game.get_build_timer() <= 0 else f"Time remaining: {game.get_build_timer():.0f}s", True, (0, 0, 255)), (100, 150))
            elif game.shooter_mode_enabled:
                screen.blit(font.render(
                    f"Balls remaining: {game.shooter_ammo}",True, (0, 0, 255)), (100, 150))


            # Really shouldn't happen
            if game.active_level is not None:
                for i, condition in enumerate(game.active_level.builder_conditions if game.builder_mode_enabled else game.active_level.shooter_conditions):
                    screen.blit(font.render(condition.text_cb(can_list) + ("" if condition.check(can_list) else "   X"), True, (0, 255, 0) if condition.check(can_list) else (255, 0, 0)), (25, 25 + 50 * i))
        else:
            # Draw end-of-match score here
            screen.fill("Black")

        pygame.display.flip()
        clock.tick(50)
        space.step(1/50)


if __name__ == "__main__":
    sys.exit(main())