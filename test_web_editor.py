"""Regression test untuk viewer/editor skyline pada UI web release."""

import base64
import unittest

import cv2

import web_app
from core.sample_generator import generate_synthetic_horizon


class WebSkylineEditorTests(unittest.TestCase):
    def test_manual_horizon_and_object_are_saved(self):
        image = generate_synthetic_horizon(width=900, height=500)
        ok, encoded = cv2.imencode(".jpg", image)
        self.assertTrue(ok)
        client = web_app.app.test_client()
        response = client.post(
            "/api/analyze",
            json={
                "image_base64": "data:image/jpeg;base64," + base64.b64encode(encoded).decode(),
                "azimuth": 270.0,
                "tilt": 0.0,
                "hfov": 60.0,
                "latitude": -7.98,
                "longitude": 110.3061,
                "altitude": 45.0,
            },
        )
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertIn("raw_base64", result)
        self.assertEqual(len(result["horizon_y"]), result["image_width"])

        horizon = result["horizon_y"]
        center = len(horizon) // 2
        horizon[center] = max(0.0, horizon[center] - 12.0)
        objects = list(result["prominent_objects"])
        objects.append(
            {
                "label": "Menara Manual",
                "x": center,
                "x_start": center - 5,
                "x_end": center + 5,
                "source": "manual_annotation",
                "is_manual": True,
            }
        )
        response = client.post(
            "/api/update_skyline",
            json={"horizon_y": horizon, "objects": objects, "target_az": 270.0},
        )
        self.assertEqual(response.status_code, 200)
        updated = response.get_json()
        manual = updated["prominent_objects"][-1]
        self.assertTrue(manual["is_manual"])
        self.assertEqual(manual["source"], "manual_annotation")
        self.assertEqual(manual["label"], "Menara Manual")
        self.assertGreater(manual["az_end"], manual["az_start"])
        self.assertGreaterEqual(min(updated["profile_curve"]["el"]), 0.0)
        self.assertEqual(
            web_app.LAST_ANALYSIS["profile_data"]["prominent_obstacles"][-1]["label"],
            "Menara Manual",
        )


if __name__ == "__main__":
    unittest.main()
