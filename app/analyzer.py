"""DeepLens - Core Analysis Engine

Multi-layered analysis to detect AI-generated images and videos.
Uses ELA, metadata inspection, color distribution, noise patterns,
edge consistency, and frequency domain analysis.
"""

import io
import os
import base64
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageChops, ImageEnhance
from PIL.ExifTags import TAGS


class DeepLensAnalyzer:
    """Main analysis engine for detecting AI-generated content."""

    AI_SOFTWARE_KEYWORDS = [
        "midjourney", "dall-e", "dalle", "stable diffusion", "stablediffusion",
        "craiyon", "imagen", "parti", "firefly", "copilot", "bing image",
        "leonardo.ai", "playground ai", "dreamstudio", "nightcafe", "wombo",
        "deepai", "generated", "synthetic", "diffusion", "neural",
    ]

    AI_DIMENSIONS = {
        (512, 512), (1024, 1024), (768, 768),
        (1024, 768), (768, 1024), (512, 768), (768, 512),
        (1024, 1792), (1792, 1024), (896, 1152), (1152, 896),
    }

    CAMERA_TAGS = {271, 272, 274, 270, 273, 306}

    def analyze_image(self, file_path: str) -> dict:
        """Run full analysis pipeline on a single image."""
        try:
            pil_image = Image.open(file_path)
        except Exception as e:
            return {"error": f"Cannot open image: {e}"}

        cv_image = cv2.imread(file_path, cv2.IMREAD_COLOR)
        if cv_image is None:
            return {"error": "Cannot read image with OpenCV"}

        ela = self._ela_analysis(file_path, pil_image)
        metadata = self._metadata_analysis(file_path, pil_image)
        color = self._color_analysis(cv_image)
        noise = self._noise_analysis(cv_image)
        edge = self._edge_analysis(cv_image)
        freq = self._frequency_analysis(cv_image)

        overall = self._calculate_overall({
            "ela": ela,
            "metadata": metadata,
            "color": color,
            "noise": noise,
            "edge": edge,
            "frequency": freq,
        })

        preview_b64 = self._image_to_base64(pil_image, max_size=600)

        return {
            "type": "image",
            "dimensions": {"width": pil_image.width, "height": pil_image.height},
            "format": pil_image.format or "UNKNOWN",
            "preview": preview_b64,
            "analyses": {
                "ela": ela,
                "metadata": metadata,
                "color": color,
                "noise": noise,
                "edge": edge,
                "frequency": freq,
            },
            "overall": overall,
        }

    def analyze_video(self, file_path: str, max_frames: int = 20) -> dict:
        """Extract frames from video and analyse each, then aggregate."""
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            return {"error": "Cannot open video file"}

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps else 0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        frame_indices = np.linspace(0, max(0, total_frames - 1), max_frames, dtype=int)
        frames = []
        for idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            ret, frame = cap.read()
            if ret:
                frames.append(frame)
        cap.release()

        if not frames:
            return {"error": "Could not extract frames from video"}

        frame_results = []
        for i, frame in enumerate(frames):
            tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            cv2.imwrite(tmp.name, frame)
            try:
                pil_img = Image.open(tmp.name)
                r = {
                    "frame_index": int(frame_indices[i]),
                    "ela": self._ela_analysis(tmp.name, pil_img),
                    "color": self._color_analysis(frame),
                    "noise": self._noise_analysis(frame),
                    "edge": self._edge_analysis(frame),
                }
                frame_results.append(r)
            finally:
                os.unlink(tmp.name)

        temporal = self._temporal_consistency(frames)

        avg_scores = {}
        for key in ("ela", "color", "noise", "edge"):
            vals = [fr[key]["score"] for fr in frame_results if "score" in fr[key]]
            avg_scores[key] = float(np.mean(vals)) if vals else 0.5

        overall = self._calculate_overall(avg_scores)

        thumb_b64 = self._cv_to_base64(frames[len(frames) // 2], max_size=400)

        return {
            "type": "video",
            "dimensions": {"width": width, "height": height},
            "duration_seconds": round(duration, 2),
            "fps": round(fps, 2),
            "total_frames": total_frames,
            "frames_analyzed": len(frame_results),
            "preview": thumb_b64,
            "analyses": {
                "frame_results": frame_results,
                "temporal": temporal,
            },
            "overall": overall,
        }

    # ------------------------------------------------------------------ #
    #  ELA — Error Level Analysis                                         #
    # ------------------------------------------------------------------ #
    def _ela_analysis(self, path: str, pil_img: Image.Image) -> dict:
        original = pil_img.convert("RGB")
        buf = io.BytesIO()
        original.save(buf, "JPEG", quality=75)
        buf.seek(0)
        resaved = Image.open(buf).convert("RGB")

        diff = ImageChops.difference(original, resaved)
        diff_enhanced = ImageEnhance.Brightness(diff).enhance(10)
        diff_gray = diff.convert("L")
        arr = np.array(diff_gray, dtype=np.float64)

        mean_d = float(np.mean(arr))
        std_d = float(np.std(arr))
        cv_val = std_d / (mean_d + 1e-6)

        score = float(np.clip((cv_val - 0.2) / 0.6, 0.0, 1.0))

        vis = self._b64_from_pil(diff_enhanced)

        return {
            "score": round(score, 4),
            "mean_difference": round(mean_d, 4),
            "std_difference": round(std_d, 4),
            "coefficient_of_variation": round(cv_val, 4),
            "visualization": vis,
            "description": self._ela_desc(score),
        }

    # ------------------------------------------------------------------ #
    #  Metadata                                                           #
    # ------------------------------------------------------------------ #
    def _metadata_analysis(self, path: str, pil_img: Image.Image) -> dict:
        exif = {}
        try:
            raw_exif = pil_img.getexif()
            for tag_id, value in raw_exif.items():
                tag_name = TAGS.get(tag_id, str(tag_id))
                if isinstance(value, bytes):
                    value = value.decode(errors="replace")
                exif[tag_name] = value
        except Exception:
            pass

        ai_hits: list[str] = []
        for tag_name, value in exif.items():
            if not isinstance(value, str):
                continue
            vl = value.lower()
            for kw in self.AI_SOFTWARE_KEYWORDS:
                if kw in vl:
                    ai_hits.append(f"{tag_name}: {value}")
                    break

        has_camera = any(str(t) in exif or t in exif for t in self.CAMERA_TAGS)
        has_gps = "GPSInfo" in exif
        w, h = pil_img.size
        has_ai_dims = (w, h) in self.AI_DIMENSIONS

        score = 0.5
        if ai_hits:
            score += len(ai_hits) * 0.15
        if not has_camera:
            score += 0.12
        if not has_gps:
            score += 0.04
        if has_ai_dims:
            score += 0.08
        score = float(np.clip(score, 0.0, 1.0))

        return {
            "score": round(score, 4),
            "ai_indicators": ai_hits,
            "has_camera_info": has_camera,
            "has_gps": has_gps,
            "has_ai_dimensions": has_ai_dims,
            "metadata": {k: str(v) for k, v in list(exif.items())[:30]},
            "description": self._metadata_desc(score, ai_hits),
        }

    # ------------------------------------------------------------------ #
    #  Colour distribution                                                #
    # ------------------------------------------------------------------ #
    def _color_analysis(self, cv_img) -> dict:
        hsv = cv2.cvtColor(cv_img, cv2.COLOR_BGR2HSV)
        h, s, _ = cv2.split(hsv)
        b_ch, g_ch, r_ch = cv2.split(cv_img)

        sat_std = float(np.std(s)) / 255.0
        hue_std = float(np.std(h)) / 180.0

        hist_h = cv2.calcHist([h], [0], None, [180], [0, 180])
        hist_h = hist_h / (hist_h.sum() + 1e-6)
        entropy_h = float(-np.sum(hist_h[hist_h > 0] * np.log2(hist_h[hist_h > 0] + 1e-6)))
        entropy_norm = entropy_h / np.log2(180)

        corr_rg = float(np.corrcoef(r_ch.ravel(), g_ch.ravel())[0, 1])
        corr_rb = float(np.corrcoef(r_ch.ravel(), b_ch.ravel())[0, 1])
        corr_gb = float(np.corrcoef(g_ch.ravel(), b_ch.ravel())[0, 1])
        avg_corr = (corr_rg + corr_rb + corr_gb) / 3.0

        score = float(np.clip(entropy_norm * 0.45 + sat_std * 0.25 + max(avg_corr, 0) * 0.30, 0, 1))

        hist_img = self._color_histogram_b64(cv_img)

        return {
            "score": round(score, 4),
            "saturation_std": round(sat_std, 4),
            "hue_entropy": round(entropy_norm, 4),
            "channel_correlation": round(avg_corr, 4),
            "histogram": hist_img,
            "description": self._color_desc(score),
        }

    # ------------------------------------------------------------------ #
    #  Noise patterns                                                     #
    # ------------------------------------------------------------------ #
    def _noise_analysis(self, cv_img) -> dict:
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)

        lap_var = float(np.var(cv2.Laplacian(gray, cv2.CV_64F)))

        med_filt = cv2.medianBlur(gray, 3)
        noise = gray.astype(np.float64) - med_filt.astype(np.float64)
        noise_mad = float(np.median(np.abs(noise)))
        noise_std = float(np.std(noise))

        f = np.fft.fft2(gray.astype(np.float64))
        fshift = np.fft.fftshift(f)
        mag = np.abs(fshift)
        rows, cols = gray.shape
        crow, ccol = rows // 2, cols // 2
        r = min(rows, cols) // 4
        y, x = np.ogrid[:rows, :cols]
        outer = ((x - ccol) ** 2 + (y - crow) ** 2) > r ** 2
        hf = float(np.mean(mag[outer]))
        lf = float(np.mean(mag[~outer]))
        freq_ratio = hf / (lf + 1e-6)

        block = 64
        noise_levels = []
        for i in range(0, rows - block, block):
            for j in range(0, cols - block, block):
                blk = gray[i:i + block, j:j + block]
                nl = float(np.std(blk.astype(np.float64) -
                                  cv2.medianBlur(blk, 3).astype(np.float64)))
                noise_levels.append(nl)
        noise_consistency = float(np.std(noise_levels) / (np.mean(noise_levels) + 1e-6)) if noise_levels else 0.5

        optimal = 8.0
        level_score = 1.0 - min(1.0, abs(noise_mad - optimal) / optimal)
        consist_score = 1.0 - min(1.0, noise_consistency)
        freq_score = min(1.0, freq_ratio * 10)
        score = float(np.clip(level_score * 0.4 + consist_score * 0.3 + freq_score * 0.3, 0, 1))

        return {
            "score": round(score, 4),
            "noise_level": round(noise_mad, 4),
            "laplacian_variance": round(lap_var, 4),
            "frequency_ratio": round(freq_ratio, 4),
            "noise_consistency": round(noise_consistency, 4),
            "description": self._noise_desc(score),
        }

    # ------------------------------------------------------------------ #
    #  Edge consistency                                                   #
    # ------------------------------------------------------------------ #
    def _edge_analysis(self, cv_img) -> dict:
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        edge_density = float(np.sum(edges > 0) / edges.size)

        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        angle = np.arctan2(sobely, sobelx)

        angle_hist, _ = np.histogram(angle[edges > 0], bins=36, range=(-np.pi, np.pi))
        angle_hist = angle_hist / (angle_hist.sum() + 1e-6)
        angle_ent = float(-np.sum(angle_hist[angle_hist > 0] * np.log2(angle_hist[angle_hist > 0] + 1e-6)))
        angle_ent_norm = angle_ent / np.log2(36)

        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges_b = cv2.Canny(blurred, 50, 150)
        edge_consistency = float(np.sum(edges == edges_b) / edges.size)

        optimal_d = 0.1
        density_score = 1.0 - min(1.0, abs(edge_density - optimal_d) / optimal_d)
        score = float(np.clip(density_score * 0.3 + angle_ent_norm * 0.4 + edge_consistency * 0.3, 0, 1))

        edge_vis = self._b64_from_cv(edges)

        return {
            "score": round(score, 4),
            "edge_density": round(edge_density, 4),
            "direction_entropy": round(angle_ent_norm, 4),
            "edge_consistency": round(edge_consistency, 4),
            "visualization": edge_vis,
            "description": self._edge_desc(score),
        }

    # ------------------------------------------------------------------ #
    #  Frequency domain                                                   #
    # ------------------------------------------------------------------ #
    def _frequency_analysis(self, cv_img) -> dict:
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY).astype(np.float64)
        f = np.fft.fft2(gray)
        fshift = np.fft.fftshift(f)
        magnitude = np.log(np.abs(fshift) + 1)
        rows, cols = gray.shape
        crow, ccol = rows // 2, cols // 2

        def ring_mean(r_min, r_max):
            y, x = np.ogrid[:rows, :cols]
            dist = np.sqrt((x - ccol) ** 2 + (y - crow) ** 2)
            mask = (dist >= r_min) & (dist < r_max)
            return float(np.mean(magnitude[mask])) if mask.any() else 0.0

        max_r = min(rows, cols) // 2
        low = ring_mean(0, max_r // 4)
        mid = ring_mean(max_r // 4, max_r // 2)
        high = ring_mean(max_r // 2, max_r)

        total = low + mid + high + 1e-6
        high_ratio = high / total
        mid_ratio = mid / total

        score = float(np.clip(mid_ratio * 0.5 + high_ratio * 1.5, 0, 1))

        mag_vis = self._b64_from_cv(
            cv2.normalize(magnitude, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        )

        return {
            "score": round(score, 4),
            "low_freq_energy": round(low, 4),
            "mid_freq_energy": round(mid, 4),
            "high_freq_energy": round(high, 4),
            "high_freq_ratio": round(high_ratio, 4),
            "spectrum": mag_vis,
            "description": self._freq_desc(score),
        }

    # ------------------------------------------------------------------ #
    #  Temporal consistency (video)                                       #
    # ------------------------------------------------------------------ #
    def _temporal_consistency(self, frames: list) -> dict:
        if len(frames) < 2:
            return {"score": 0.5, "description": "Not enough frames to analyse temporal consistency."}

        sims = []
        for i in range(len(frames) - 1):
            g1 = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)
            g2 = cv2.cvtColor(frames[i + 1], cv2.COLOR_BGR2GRAY)
            if g1.shape != g2.shape:
                g2 = cv2.resize(g2, (g1.shape[1], g1.shape[0]))
            mse = float(np.mean((g1.astype(np.float64) - g2.astype(np.float64)) ** 2))
            sims.append(1.0 / (1.0 + mse / 1000.0))

        sim_std = float(np.std(sims))
        score = float(np.clip(1.0 - sim_std * 5, 0, 1))

        return {
            "score": round(score, 4),
            "average_similarity": round(float(np.mean(sims)), 4),
            "similarity_std": round(sim_std, 4),
            "description": "Frames are temporally consistent." if score > 0.6
                           else "Temporal inconsistencies detected — possible synthetic generation.",
        }

    # ------------------------------------------------------------------ #
    #  Scoring                                                            #
    # ------------------------------------------------------------------ #
    def _calculate_overall(self, analyses: dict) -> dict:
        weights = {
            "ela": 0.22, "metadata": 0.12, "color": 0.22,
            "noise": 0.18, "edge": 0.13, "frequency": 0.13,
        }
        scores = {}
        for key, w in weights.items():
            a = analyses.get(key, {})
            scores[key] = a.get("score", 0.5)

        overall = sum(scores[k] * weights[k] for k in weights)
        overall = float(np.clip(overall, 0, 1))

        if overall >= 0.65:
            verdict = "Likely Real"
            confidence = "high" if overall >= 0.75 else "medium"
        elif overall >= 0.45:
            verdict = "Inconclusive"
            confidence = "low"
        else:
            verdict = "Likely AI-Generated"
            confidence = "high" if overall <= 0.30 else "medium"

        return {
            "overall_score": round(overall, 4),
            "verdict": verdict,
            "confidence": confidence,
            "individual_scores": {k: round(v, 4) for k, v in scores.items()},
        }

    # ------------------------------------------------------------------ #
    #  Helpers                                                            #
    # ------------------------------------------------------------------ #
    def _image_to_base64(self, pil_img: Image.Image, max_size: int = 600) -> str:
        img = pil_img.copy()
        if img.mode != "RGB":
            img = img.convert("RGB")
        if max(img.size) > max_size:
            img.thumbnail((max_size, max_size), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=80)
        return base64.b64encode(buf.getvalue()).decode()

    def _cv_to_base64(self, frame, max_size: int = 400) -> str:
        h, w = frame.shape[:2]
        if max(h, w) > max_size:
            scale = max_size / max(h, w)
            frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return base64.b64encode(buf).decode()

    def _b64_from_pil(self, pil_img: Image.Image) -> str:
        if pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")
        buf = io.BytesIO()
        pil_img.save(buf, "JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode()

    def _b64_from_cv(self, cv_img) -> str:
        if len(cv_img.shape) == 2:
            cv_img = cv2.cvtColor(cv_img, cv2.COLOR_GRAY2BGR)
        _, buf = cv2.imencode(".jpg", cv_img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return base64.b64encode(buf).decode()

    def _color_histogram_b64(self, cv_img) -> str:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        colors = ("b", "g", "r")
        fig, ax = plt.subplots(figsize=(4, 2.5), dpi=80)
        fig.patch.set_facecolor("#1a1a2e")
        ax.set_facecolor("#1a1a2e")
        for i, col in enumerate(colors):
            hist = cv2.calcHist([cv_img], [i], None, [256], [0, 256])
            ax.plot(hist, color=col, alpha=0.7, linewidth=0.8)
        ax.set_xlim([0, 256])
        ax.tick_params(colors="#aaa", labelsize=7)
        for spine in ax.spines.values():
            spine.set_color("#333")
        plt.tight_layout(pad=0.3)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", facecolor=fig.get_facecolor(), dpi=80)
        plt.close(fig)
        return base64.b64encode(buf.getvalue()).decode()

    # ------------------------------------------------------------------ #
    #  Description generators                                             #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _ela_desc(score: float) -> str:
        if score >= 0.7:
            return "High variance in error levels — typical of authentic photographs with natural sensor noise."
        if score >= 0.4:
            return "Moderate error-level variance — inconclusive; could be edited or AI-generated."
        return "Low, uniform error levels — a strong indicator of AI-generated or heavily processed imagery."

    @staticmethod
    def _metadata_desc(score: float, hits: list) -> str:
        parts = []
        if hits:
            parts.append(f"AI-related metadata tags found: {'; '.join(hits[:3])}.")
        if score >= 0.65:
            parts.append("Metadata suggests this image was captured by a real camera.")
        elif score <= 0.40:
            parts.append("Metadata is consistent with AI-generated content (missing camera info or AI tool tags).")
        else:
            parts.append("Metadata is inconclusive.")
        return " ".join(parts) if parts else "No notable metadata findings."

    @staticmethod
    def _color_desc(score: float) -> str:
        if score >= 0.7:
            return "Rich, natural colour distribution with high entropy — consistent with real photography."
        if score >= 0.4:
            return "Moderate colour characteristics — could be real or AI-generated."
        return "Unusual colour distribution patterns — may indicate synthetic generation."

    @staticmethod
    def _noise_desc(score: float) -> str:
        if score >= 0.7:
            return "Natural noise patterns consistent with camera sensor noise."
        if score >= 0.4:
            return "Noise patterns are moderate — inconclusive."
        return "Unusual noise profile — may indicate AI generation or heavy processing."

    @staticmethod
    def _edge_desc(score: float) -> str:
        if score >= 0.7:
            return "Natural edge patterns with expected direction diversity."
        if score >= 0.4:
            return "Edge patterns are moderate — inconclusive."
        return "Unusual edge consistency or distribution — potential synthetic indicator."

    @staticmethod
    def _freq_desc(score: float) -> str:
        if score >= 0.65:
            return "Frequency spectrum consistent with real photographs."
        if score >= 0.4:
            return "Frequency analysis is inconclusive."
        return "Unusual frequency patterns detected — common in AI-generated images."
