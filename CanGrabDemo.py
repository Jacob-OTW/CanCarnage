import sys
import pygame
import pymunk
import random


def spawn_circle(pos, space):
    new_body = pymunk.Body()
    new_body.position = pos

    circle = pymunk.Poly.create_box(new_body, (20, 50))
    circle.mass = 20
    circle.elasticity = 0.2
    circle.friction = 1
    space.add(new_body, circle)

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

    pymunk.pygame_util.positive_y_is_up = True
    space = pymunk.Space()
    space.gravity = 0, -981

    create_boundaries(space, screen.width, screen.height)

    options = pymunk.pygame_util.DrawOptions(screen)
    space.debug_draw(options)

    # Mouse dragging variables
    mouse_body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
    mouse_joint = None

    for i in range(15):
        spawn_circle((screen.width / 2 + random.randint(-150, 150), screen.height / 2), space)
    while True:
        for event in pygame.event.get():
            match event.type:
                case pygame.QUIT:
                    return
                case pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        p = pymunk.Vec2d(*pymunk.pygame_util.to_pygame(event.pos, screen))
                        hit = space.point_query_nearest(p, 1, pymunk.ShapeFilter())
                        if hit and hit.shape.body.body_type == pymunk.Body.DYNAMIC:
                            dragged_body = hit.shape.body
                            mouse_joint = pymunk.PivotJoint(mouse_body, dragged_body, (0, 0),
                                                            dragged_body.world_to_local(p))
                            mouse_joint.max_force = 50000
                            mouse_joint.error_bias = (1 - 0.15) ** 60
                            space.add(mouse_joint)
                case pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        if mouse_joint is not None:
                            space.remove(mouse_joint)
                            mouse_joint = None

        # Update mouse position
        mouse_pos = pymunk.pygame_util.get_mouse_pos(screen)
        mouse_body.position = mouse_pos


        screen.fill("White")
        space.debug_draw(options)

        pygame.display.flip()
        clock.tick(50)
        space.step(1/50)


if __name__ == "__main__":
    sys.exit(main())