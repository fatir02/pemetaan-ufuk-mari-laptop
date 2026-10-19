"""Regression test khusus kontur objek kecil dan baseline elevasi relatif."""

import unittest

import cv2
import numpy as np

from core.cv_engine import HorizonDetector


def make_tower_scene(tower_x=None, segmented=False):
    """Buat ufuk datar dengan menara kisi tipis pada posisi yang diminta."""
    width, height = 640, 360
    image = np.full((height, width, 3), (190, 205, 225), dtype=np.uint8)
    ground_y = 235
    image[ground_y:, :] = (35, 40, 45)

    if tower_x is not None:
        tower_x = min(max(0, tower_x), width - 6)
        if segmented:
            # Fragmen vertikal dengan gap pendek meniru menara kisi/JPEG breakup.
            for top in range(177, ground_y, 9):
                cv2.line(
                    image,
                    (tower_x + 2, min(ground_y, top + 5)),
                    (tower_x + 2, top),
                    (20, 20, 20),
                    2,
                )
        else:
            cv2.line(image, (tower_x, ground_y), (tower_x + 2, 175), (20, 20, 20), 2)
            cv2.line(image, (tower_x + 5, ground_y), (tower_x + 3, 175), (20, 20, 20), 2)
            for y in range(180, ground_y, 8):
                cv2.line(image, (tower_x, y), (tower_x + 5, y), (20, 20, 20), 1)
    return image, ground_y


def make_extreme_cloud_scene():
    """Langit dengan cloud edge kuat serta pohon yang menyentuh awan."""
    width, height = 640, 480
    image = np.zeros((height, width, 3), dtype=np.uint8)
    for y in range(height):
        t = y / float(height - 1)
        image[y, :] = (190 - 50 * t, 150 + 40 * t, 100 + 100 * t)

    clouds = [
        (130, 250, 120, 35),
        (320, 290, 150, 45),
        (500, 320, 120, 55),
        (400, 210, 80, 25),
    ]
    for cx, cy, rx, ry in clouds:
        cv2.ellipse(image, (cx, cy), (rx, ry), 0, 0, 360, (75, 80, 85), -1)
        cv2.ellipse(image, (cx, cy - 8), (rx - 10, max(5, ry - 12)), 0, 180, 360, (235, 235, 240), -1)

    horizon_y = 390
    image[horizon_y:420, :] = (70, 80, 85)
    image[420:, :] = (25, 35, 28)
    # Pohon menyentuh cloud blob; baseline tidak boleh membawa seluruh awan.
    cv2.rectangle(image, (470, 310), (478, 420), (25, 35, 28), -1)
    cv2.circle(image, (474, 320), 35, (25, 45, 30), -1)
    return image, horizon_y


class SmallObstacleDetectionTests(unittest.TestCase):
    def analyze(self, tower_x=None, segmented=False):
        image, ground_y = make_tower_scene(tower_x, segmented)
        detector = HorizonDetector()
        horizon, _ = detector.detect_horizon(image)
        profile = detector.compute_horizon_profile(
            horizon_y=horizon,
            img_w=image.shape[1],
            img_h=image.shape[0],
            az_center=270.0,
            hfov=60.0,
        )
        return detector, horizon, profile, ground_y

    def test_center_lattice_tower_is_preserved(self):
        detector, horizon, profile, ground_y = self.analyze(315)
        self.assertTrue(detector.last_detail_obstacles)
        self.assertLess(float(np.min(horizon[313:323])), ground_y - 45)
        self.assertTrue(any(obj["source"] == "detail_vertical" for obj in profile["prominent_obstacles"]))
        tower_objects = [obj for obj in profile["prominent_obstacles"] if obj["source"] == "detail_vertical"]
        self.assertTrue(any(obj["object_class"] == "tower_antenna" for obj in tower_objects))
        self.assertTrue(all("classification_confidence" in obj for obj in tower_objects))

    def test_segmented_tower_with_short_gaps_is_preserved(self):
        detector, horizon, _, ground_y = self.analyze(315, segmented=True)
        self.assertTrue(detector.last_detail_obstacles)
        self.assertLess(float(np.min(horizon[314:321])), ground_y - 40)

    def test_low_contrast_tower_is_preserved(self):
        image, ground_y = make_tower_scene(None)
        tower_x = 315
        # Hanya sekitar 18 level lebih gelap dari langit; mewakili kabut tipis.
        color = (172, 187, 207)
        cv2.line(image, (tower_x, ground_y), (tower_x + 2, 175), color, 2)
        cv2.line(image, (tower_x + 5, ground_y), (tower_x + 3, 175), color, 2)
        for y in range(180, ground_y, 8):
            cv2.line(image, (tower_x, y), (tower_x + 5, y), color, 1)

        detector = HorizonDetector()
        horizon, _ = detector.detect_horizon(image)
        self.assertTrue(detector.last_detail_obstacles)
        self.assertLess(float(np.min(horizon[313:323])), ground_y - 40)

    def test_towers_at_active_image_endpoints_are_reported(self):
        for x in (1, 634):
            with self.subTest(x=x):
                detector, _, profile, _ = self.analyze(x)
                self.assertTrue(detector.last_detail_obstacles)
                self.assertTrue(any(obj["is_endpoint"] for obj in profile["prominent_obstacles"]))

    def test_flat_horizon_has_no_false_detail_obstacle(self):
        detector, _, _, _ = self.analyze(None)
        self.assertEqual(detector.last_detail_obstacles, [])

    def test_extreme_cloud_edges_do_not_replace_bottom_horizon(self):
        image, expected_y = make_extreme_cloud_scene()
        detector = HorizonDetector()
        horizon, _ = detector.detect_horizon(image)

        # Sebagian besar kontur harus mengikuti ufuk/permukaan bawah, bukan
        # cloud edge kuat yang berada 70-180 piksel lebih tinggi.
        self.assertLess(abs(float(np.median(horizon)) - expected_y), 4.0)
        outside_tree = np.concatenate((horizon[:440], horizon[510:]))
        self.assertGreater(float(np.percentile(outside_tree, 5)), expected_y - 8.0)
        # Pohon tetap boleh dikembalikan oleh jalur detail sebagai objek.
        self.assertTrue(any(465 <= obs["x"] <= 485 for obs in detector.last_detail_obstacles))

    def test_green_tree_skyline_object_is_labeled_as_vegetation(self):
        image, ground_y = make_tower_scene(None)
        x = 320
        cv2.rectangle(image, (x - 3, ground_y - 45), (x + 3, ground_y), (25, 70, 35), -1)
        cv2.circle(image, (x, ground_y - 55), 24, (30, 105, 45), -1)
        cv2.circle(image, (x - 15, ground_y - 48), 17, (35, 115, 50), -1)
        cv2.circle(image, (x + 15, ground_y - 48), 17, (28, 95, 40), -1)

        detector = HorizonDetector()
        horizon, _ = detector.detect_horizon(image)
        profile = detector.compute_horizon_profile(horizon, image.shape[1], image.shape[0], 270.0, 60.0)
        nearby = [obj for obj in profile["prominent_obstacles"] if abs(obj["x"] - x) < 35]
        self.assertTrue(nearby)
        self.assertTrue(any(obj["object_class"] == "vegetation" for obj in nearby))
        self.assertTrue(any(obj["label"] == "Vegetasi/Pohon" for obj in nearby))

    def test_solid_pitched_roof_is_labeled_as_building(self):
        image, ground_y = make_tower_scene(None)
        cv2.rectangle(image, (270, 205), (370, ground_y), (80, 85, 90), -1)
        roof = np.array([[260, 205], [320, 170], [380, 205]], dtype=np.int32)
        cv2.fillPoly(image, [roof], (65, 70, 75))
        for y in (218, 232):
            cv2.line(image, (275, y), (365, y), (150, 155, 160), 2)

        detector = HorizonDetector()
        horizon, _ = detector.detect_horizon(image)
        profile = detector.compute_horizon_profile(horizon, image.shape[1], image.shape[0], 270.0, 60.0)
        nearby = [obj for obj in profile["prominent_obstacles"] if 250 <= obj["x"] <= 390]
        self.assertTrue(nearby)
        self.assertTrue(any(obj["object_class"] == "building_roof" for obj in nearby))
        self.assertTrue(any(obj["label"] == "Bangunan/Atap" for obj in nearby))

    def test_smooth_solid_hill_is_not_labeled_as_building(self):
        width, height = 640, 360
        ground_y = 250
        image = np.full((height, width, 3), (190, 205, 225), dtype=np.uint8)
        xs = np.arange(width)
        synthetic_horizon = np.full(width, ground_y, dtype=np.float64)
        hill = (xs >= 120) & (xs <= 520)
        synthetic_horizon[hill] -= 75.0 * np.sin(np.pi * (xs[hill] - 120) / 400.0)
        polygon = np.column_stack((xs, synthetic_horizon.astype(np.int32)))
        polygon = np.vstack((polygon, [[width - 1, height - 1], [0, height - 1]])).astype(np.int32)
        cv2.fillPoly(image, [polygon], (45, 50, 55))

        detector = HorizonDetector()
        detector.last_image_bgr = image
        result = detector._classify_skyline_obstacle(
            120, 520, 320, synthetic_horizon[320], synthetic_horizon
        )
        self.assertEqual(result["object_class"] if "object_class" in result else result["class"], "terrain")
        self.assertEqual(result["label"], "Bukit/Terrain")
        self.assertEqual(result["features"]["horizontal_line_count"], 0)

    def test_tower_above_busy_urban_mass_remains_tower(self):
        image, ground_y = make_tower_scene(None)
        # Massa kota yang lebar/solid di bawah skyline tidak boleh menjadi veto
        # bagi batang menara yang jelas ramping di atasnya.
        for x in range(0, image.shape[1], 32):
            top = ground_y - (8 + (x // 32) % 4 * 4)
            cv2.rectangle(image, (x, top), (min(image.shape[1] - 1, x + 27), ground_y), (55, 62, 68), -1)
            cv2.line(image, (x + 3, top + 6), (min(image.shape[1] - 1, x + 23), top + 6), (120, 125, 130), 1)

        tower_x = 315
        cv2.line(image, (tower_x, ground_y), (tower_x + 2, 145), (20, 20, 20), 2)
        cv2.line(image, (tower_x + 7, ground_y), (tower_x + 4, 145), (20, 20, 20), 2)
        for y in range(150, ground_y, 9):
            cv2.line(image, (tower_x, y), (tower_x + 7, y), (20, 20, 20), 1)

        detector = HorizonDetector()
        horizon, _ = detector.detect_horizon(image)
        profile = detector.compute_horizon_profile(horizon, image.shape[1], image.shape[0], 270.0, 60.0)
        nearby = [obj for obj in profile["prominent_obstacles"] if abs(obj["x"] - tower_x) < 20]
        self.assertTrue(nearby)
        self.assertTrue(any(obj["object_class"] == "tower_antenna" for obj in nearby))
        self.assertTrue(any(obj["classification_features"]["strong_slender_detail"] for obj in nearby))

    def test_lowest_profile_point_remains_relative_zero(self):
        _, _, profile, _ = self.analyze(315)
        self.assertAlmostEqual(float(np.min(profile["elevations"])), 0.0, places=9)
        self.assertEqual(profile["elevation_reference"], "minimum_horizon_profile")


if __name__ == "__main__":
    unittest.main()
