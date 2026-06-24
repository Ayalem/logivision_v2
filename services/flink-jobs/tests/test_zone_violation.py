"""
Tests unitaires pour la détection de zone interdite.
Ces tests ne nécessitent pas Kafka — on teste la logique pure.
"""

import pytest
from jobs.zone_violation import (
    is_point_in_zone,
    point_in_polygon_ray_casting,
)


class TestPointInPolygon:
    """Tests pour l'algorithme de détection point-dans-polygone."""
    
    # Polygone carré : (100,100) → (200,100) → (200,200) → (100,200)
    SQUARE_POLYGON = [
        (100, 100),
        (200, 100),
        (200, 200),
        (100, 200),
    ]
    
    def test_point_inside_square(self):
        """Un point au centre du carré doit être détecté."""
        assert is_point_in_zone(150, 150, self.SQUARE_POLYGON) is True
    
    def test_point_outside_square(self):
        """Un point clairement à l'extérieur ne doit pas être détecté."""
        assert is_point_in_zone(50, 50, self.SQUARE_POLYGON) is False
        assert is_point_in_zone(300, 300, self.SQUARE_POLYGON) is False
        assert is_point_in_zone(0, 0, self.SQUARE_POLYGON) is False
    
    def test_point_near_edge(self):
        """Un point juste à l'extérieur du bord ne doit pas déclencher."""
        assert is_point_in_zone(99, 150, self.SQUARE_POLYGON) is False
        assert is_point_in_zone(201, 150, self.SQUARE_POLYGON) is False
    
    def test_triangle_polygon(self):
        """Test avec un polygone triangulaire."""
        triangle = [(0, 0), (100, 0), (50, 100)]
        assert is_point_in_zone(50, 50, triangle) is True
        assert is_point_in_zone(90, 90, triangle) is False
    
    def test_large_warehouse_zone(self):
        """Test avec des coordonnées réalistes d'entrepôt (pixels caméra 640×480)."""
        forklift_zone = [(280, 0), (360, 0), (360, 480), (280, 480)]
        
        # Une personne dans le couloir → DANGER
        assert is_point_in_zone(320, 240, forklift_zone) is True
        
        # Une personne à côté → OK
        assert is_point_in_zone(100, 240, forklift_zone) is False
        assert is_point_in_zone(500, 240, forklift_zone) is False