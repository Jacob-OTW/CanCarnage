import sys
import time
import pygame
import pymunk
import pymunk.pygame_util
import random
import math

class Level:
    def __init__(self):
        self.builder_time = 60
        self.shooter_ammo = 4
        self.builder_condition_cb = None
        self.shooter_score_cb = None

class GameSingleton:
    def __init__(self):
        self.builder_mode_enabled = True
        self.builder_mode_timer = None
        self.builder_mode_max_time = 20 # In seconds

        self.shooter_mode_enabled = False
        self.shooter_max_ammo = 4
        self.shooter_ammo = self.shooter_max_ammo


    def update(self):
        if self.builder_mode_enabled and self.builder_mode_timer is not None:
            if time.time() - self.builder_mode_timer >= self.builder_mode_max_time:
                self.builder_mode_enabled = False
                self.builder_mode_timer = None

                self.shooter_mode_enabled = True
                self.shooter_ammo = self.shooter_max_ammo

        if self.shooter_mode_enabled and self.shooter_ammo <= 0:
            self.shooter_mode_enabled = False

            self.builder_mode_enabled = True
            self.builder_mode_timer = None

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
        dyn_circle.mass = 20
        dyn_circle.elasticity = 0.3
        dyn_circle.friction = 0.5

        self.dyn_bird_list.append((self.dyn_bird, dyn_circle))

        space.add(self.dyn_bird, dyn_circle)
        return self.dyn_bird

    def update(self, screen, space):
        if self.dragging_bird:
            mouse = pygame.Vector2(pymunk.pygame_util.get_mouse_pos(screen)) - self.anchor_pos
            self.bird_body.position = tuple(mouse.clamp_magnitude(self.max_draw_distance).xy + self.anchor_pos)
        else:
            self.bird_body.position = self.anchor_pos

        if self.dyn_bird and (self.dyn_bird.velocity.length < 50 or self.dyn_bird.position.length >= 5000):
            self.dyn_bird = None
            space.add(self.bird_body, self.bird_shape)

def spawn_can(pos, space) -> tuple[pymunk.Body, pymunk.Shape]:
    new_body = pymunk.Body()
    new_body.position = pos

    circle = pymunk.Poly.create_box(new_body, (20, 50))
    circle.mass = 20
    circle.elasticity = 0.2
    circle.friction = 1
    space.add(new_body, circle)
    return (new_body, circle)

def create_boundaries(space, width, height):
    rects = [
        [(width/2, height - 10), (width, 20)],
        [(width/2, 10), (width, 20)],
        [(10, height/2), (20, height)],
        [(width - 10, height/2), (20, height)]
    ]

    for pos, size in rects:
        body = pymunk.Body(body_type=pymunk.Body.STATIC)
        body.position = pos
        shape = pymunk.Poly.create_box(body, size)
        shape.elasticity = 1
        shape.friction = 0.5
        space.add(body, shape)

def main():
    pygame.init()
    screen = pygame.display.set_mode((1000, 700))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("arial", 32, pygame.font.Font.bold)

    ball_image = pygame.image.load("assets/images/ball.png")

    game = GameSingleton()

    pymunk.pygame_util.positive_y_is_up = True
    space = pymunk.Space()
    space.gravity = 0, -981

    create_boundaries(space, screen.width, screen.height)

    slingshot = SlingShot(pymunk.Vec2d(150, 150), space)

    options = pymunk.pygame_util.DrawOptions(screen)
    space.debug_draw(options)

    # Mouse dragging variables
    mouse_body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
    mouse_joint = None

    can_list = []
    can_image = pygame.image.load("assets/images/can.png")

    for i in range(15):
        can = spawn_can((screen.width / 2 + random.randint(-150, 150), screen.height / 2), space)
        can_list.append(can)
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
                        elif mouse_joint is not None and game.builder_mode_enabled:
                            space.remove(mouse_joint)
                            mouse_joint = None

        # Update mouse position
        mouse_pos = pymunk.pygame_util.get_mouse_pos(screen)
        mouse_body.position = mouse_pos

        slingshot.update(screen, space)
        game.update()

        screen.fill("White")
        space.debug_draw(options)

        for dyn_body, dyn_circle in slingshot.dyn_bird_list:
            dyn_body: pymunk.Body
            rotated_circle = pygame.transform.rotate(ball_image, math.degrees(dyn_body.angle))  # Radians to degrees
            rect = rotated_circle.get_rect(center=pymunk.pygame_util.to_pygame(dyn_body.position, screen))
            screen.blit(rotated_circle, rect.topleft)
        for can_body, can_shape in can_list:
            can_body: pymunk.Body
            rotated_can = pygame.transform.rotate(can_image, math.degrees(can_body.angle))  # Radians to degrees
            rect = rotated_can.get_rect(center=pymunk.pygame_util.to_pygame(can_body.position, screen))
            screen.blit(rotated_can, rect.topleft)

        if game.builder_mode_enabled:
            text = ""
            if game.get_build_timer() <= 0:
                text = "Drag block to start timer"
            else:
                text = f"Time remaining: {game.get_build_timer():.0f}"

            screen.blit(font.render(text, True, (0, 0, 255)), (100, 150))

        pygame.display.flip()
        clock.tick(50)
        space.step(1/50)


if __name__ == "__main__":
    sys.exit(main())