import pygame
import pymunk
import pymunk.pygame_util
import math

pygame.init()
screen = pygame.display.set_mode((800, 600))
clock = pygame.time.Clock()

# Pymunk space
space = pymunk.Space()
space.gravity = (0, 900)

draw_options = pymunk.pygame_util.DrawOptions(screen)

# Slingshot anchor
anchor_pos = pymunk.Vec2d(150, 450)

# Bird settings
bird_radius = 15
bird_body = pymunk.Body(1, pymunk.moment_for_circle(1, 0, bird_radius), body_type=pymunk.Body.KINEMATIC)
bird_body.position = anchor_pos
bird_shape = pymunk.Circle(bird_body, bird_radius)
bird_shape.elasticity = 0.8
space.add(bird_body, bird_shape)

# Flags
dragging = False

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        # Start dragging
        elif event.type == pygame.MOUSEBUTTONDOWN:
            p = pymunk.Vec2d(*pymunk.pygame_util.to_pygame(event.pos, screen))
            hit = space.point_query_nearest(p, 1, pymunk.ShapeFilter())
            if hit and hit.shape.body == bird_body:
                dragging = True

        # Stop dragging and launch
        elif event.type == pygame.MOUSEBUTTONUP:
            if dragging:
                dragging = False

                dx = anchor_pos[0] - bird_body.position[0]
                dy = anchor_pos[1] - bird_body.position[1]
                impulse = (dx * 5, dy * 5)

                dyn_bird = pymunk.Body()
                dyn_bird.position = bird_body.position

                dyn_circle = pymunk.Circle(dyn_bird, 15)
                dyn_circle.mass = 20
                dyn_circle.elasticity = 0.8

                space.add(dyn_bird, dyn_circle)
                dyn_bird.velocity = impulse

    if dragging:
        bird_body.position = pymunk.pygame_util.get_mouse_pos(screen)
    else:
        bird_body.position = anchor_pos

    screen.fill((200, 255, 255))

    # Draw slingshot band
    if dragging:
        pygame.draw.line(screen, (100, 50, 20), anchor_pos, bird_body.position, 5)

    space.debug_draw(draw_options)
    space.step(1 / 60.0)
    pygame.display.flip()
    clock.tick(60)

pygame.quit()
