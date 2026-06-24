"""
Tests unitaires pour la détection de colis stationnaires.
"""

import pytest
from jobs.stationary_detection import (
    calculate_distance,
    has_object_moved,
)


class TestMovementDetection:
    """Tests pour la détection de mouvement."""
    
    def test_no_movement(self):
        """Objet exactement au même endroit → pas bougé."""
        assert has_object_moved(100.0, 100.0, 100.0, 100.0) is False
    
    def test_small_movement_below_tolerance(self):
        """Mouvement inférieur à la tolérance → considéré comme immobile."""
        # Tolérance par défaut = 15px
        # Déplacement de 5px → immobile
        assert has_object_moved(100.0, 100.0, 105.0, 100.0) is False
    
    def test_large_movement(self):
        """Déplacement significatif → objet en mouvement."""
        # Déplacement de 50px → en mouvement
        assert has_object_moved(100.0, 100.0, 150.0, 100.0) is True
    
    def test_diagonal_movement(self):
        """Déplacement diagonal."""
        # Distance = sqrt(20² + 20²) ≈ 28.3px > 15px → en mouvement
        assert has_object_moved(0.0, 0.0, 20.0, 20.0) is True
    
    def test_distance_calculation(self):
        """Vérification du calcul de distance."""
        # Distance de (0,0) à (3,4) = 5 (triangle 3-4-5)
        distance = calculate_distance(0.0, 0.0, 3.0, 4.0)
        assert abs(distance - 5.0) < 0.001
    
    def test_custom_tolerance(self):
        """Test avec une tolérance personnalisée."""
        # Avec tolérance de 5px : déplacement de 6px = en mouvement
        assert has_object_moved(0.0, 0.0, 6.0, 0.0, tolerance=5.0) is True
        
        # Avec tolérance de 10px : déplacement de 6px = immobile
        assert has_object_moved(0.0, 0.0, 6.0, 0.0, tolerance=10.0) is False