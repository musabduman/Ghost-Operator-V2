import math
from settings import *

def calculate_lift(air_speed, wing_area=1.0, lift_coefficient=LIFT_COEFFICIENT):
    """Kaldırma kuvveti = 0.5 * rho * v^2 * S * Cl"""
    return 0.5 * AIR_DENSITY * (air_speed ** 2) * wing_area * lift_coefficient

def calculate_drag(air_speed, drag_coefficient=DRAG_COEFFICIENT, wing_area=1.0):
    """Sürükleme kuvveti = 0.5 * rho * v^2 * S * Cd"""
    return 0.5 * AIR_DENSITY * (air_speed ** 2) * wing_area * drag_coefficient

def update_velocity(velocity, thrust, lift, drag, dt):
    """Basit ivme hesabı, kütle=1 varsayılır"""
    # thrust, lift, drag vektörleri pygame.Vector2
    accel = thrust + lift + drag  # mass=1
    return velocity + accel * dt

__all__ = ['calculate_lift', 'calculate_drag', 'update_velocity']
