"""
Prodia v2 Async API — Shared Client
=====================================
ใช้ร่วมกันระหว่าง image module และ video module
Job creation + polling + price tracking ผ่าน /v2/job/async

Key endpoints:
  - POST /v2/job/async?price=true    → สร้าง Job (JSON หรือ multipart)
  - GET  /v2/job/async/:id/job.state.current  → Poll สถานะ
  - GET  /v2/job/async/:id/job.json?price=true → ผลลัพธ์ + Cost จริง

Usage:
    from prodia_client import ProdiaV2Client

    client = ProdiaV2Client(token="...")
    
    # txt2vid (JSON)
    job_id = client.create_job("inference.wan2-7.txt2vid.v1", {
        "prompt": "...", "duration": 8, "resolution": "720P", "ratio": "9:16"
    })
    
    # img2vid (multipart + input image)
    job_id = client.create_job("inference.wan2-7.img2vid.v1", {...}, inputs=[image_bytes])
    
    # poll → result + price
    result = client.wait_for_result(job_id)
    price = result.get("price", {})  # price.dollars
"""

import os
import sys
import json
import time
import logging
from typing import Optional, List, Dict, Any, Tuple

import requests

logger = logging.getLogger("prodia-client")

PRODIA_V2_BASE = "https://inference.prodia.com/v2"

# ─── Custom Errors ──────────────────────────────────────────────────────────

class ProdiaV2Error(Exception):
    """Base error for Prodia v2 Async API."""
    pass

class ProdiaJobFailedError(ProdiaV2Error):
    """Job completed but with failure status."""
    pass

class ProdiaTimeoutError(ProdiaV2Error):
    """Job polling timed out."""
    pass

class ProdiaRateLimitError(ProdiaV2Error):
    """Rate limited (429)."""
    pass

class ProdiaValidationError(ProdiaV2Error):
    """Invalid job config (400)."""
    pass


# ═══════════════════════════════════════════════════════════════════════════
# Prodia v2 Async Client
# ═══════════════════════════════════════════════════════════════════════════

class ProdiaV2Client:
    """
    Prodia v2 Async API Client
    
    รองรับ:
      - txt2img / img2img / txt2vid / img2vid
      - ?price=true → cost tracking
      - Exponential backoff polling
      - Auto-detect JSON vs multipart based on inputs
    """

    def __init__(self, token: str, base_url: str = PRODIA_V2_BASE):
        self.token = token
        self.base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        })

    # ── Public API ──────────────────────────────────────────────────────────

    def create_job(
        self,
        job_type: str,
        config: dict,
        inputs: Optional[List[bytes]] = None,
        accept: Optional[str] = None,
    ) -> str:
        """
        สร้าง Job ผ่าน Async API
        
        Auto-detect:
          - inputs=None → ส่งเป็น JSON (Content-Type: application/json)
          - inputs=[bytes] → ส่งเป็น multipart/form-data
        
        Args:
            job_type: เช่น "inference.wan2-7.img2vid.v1", "inference.nano-banana.img2img.v2"
            config: dict ของ config parameters
            inputs: list ของ bytes สำหรับ input images (optional)
            accept: output format hint (optional)
        
        Returns:
            str: jobId สำหรับ polling
        
        Raises:
            ProdiaValidationError: 400 — config ไม่ถูก
            ProdiaRateLimitError: 429
            ProdiaV2Error: อื่นๆ
        """
        endpoint = f"{self.base_url}/job/async?price=true"

        has_inputs = inputs and len(inputs) > 0

        # Build job payload
        job_payload: Dict[str, Any] = {
            "type": job_type,
            "config": config,
        }
        if accept:
            job_payload["accept"] = accept

        if has_inputs:
            # ── Multipart form-data ──
            files = [
                ("job", ("job.json", json.dumps(job_payload), "application/json")),
            ]
            for i, img_bytes in enumerate(inputs):
                files.append(("input", (f"input_{i}.png", img_bytes, "image/png")))

            logger.info(f"[Prodia] Creating job (multipart): {job_type}")
            logger.debug(f"  Config: {json.dumps(config)[:200]}")
            logger.debug(f"  Inputs: {len(inputs)} file(s)")

            try:
                resp = self._session.post(endpoint, files=files, timeout=60)
            except requests.exceptions.Timeout:
                raise ProdiaV2Error("Prodia API timeout (create_job multipart)")
            except requests.exceptions.ConnectionError as e:
                raise ProdiaV2Error(f"Prodia connection failed: {e}")
        else:
            # ── JSON ──
            logger.info(f"[Prodia] Creating job (JSON): {job_type}")
            logger.debug(f"  Config: {json.dumps(config)[:200]}")

            try:
                resp = self._session.post(
                    endpoint,
                    json=job_payload,
                    timeout=60,
                )
            except requests.exceptions.Timeout:
                raise ProdiaV2Error("Prodia API timeout (create_job JSON)")
            except requests.exceptions.ConnectionError as e:
                raise ProdiaV2Error(f"Prodia connection failed: {e}")

        # ── Handle status codes ──
        return self._handle_job_response(resp, job_type)

    # ────────────────────────────────────────────────────────────────────────

    def poll_until_processed(
        self,
        job_id: str,
        max_retries: int = 120,
        initial_delay: float = 2.0,
        backoff_factor: float = 1.0,
        max_delay: float = 5.0,
    ) -> dict:
        """
        Poll Job State จน status = "processed"
        
        NOTE: /v2/job/async/:id/job.state.current returns PLAIN TEXT status string
        (not JSON). So we parse the text directly.
        
        After processed → call get_result() for full data + price.
        
        Args:
            job_id: jobId จาก create_job()
            max_retries: สูงสุด 120 retries
            initial_delay: 2s
            backoff_factor: 1.0 (fixed interval)
            max_delay: 5s
        
        Returns:
            dict: state data (minimal)
        
        Raises:
            ProdiaTimeoutError: เกิน max_retries
            ProdiaJobFailedError: job failed
        """
        state_url = f"{self.base_url}/job/async/{job_id}/job.state.current"
        delay = min(initial_delay, max_delay)
        last_status = ""

        for attempt in range(max_retries):
            time.sleep(delay)

            try:
                resp = self._session.get(state_url, timeout=30)
            except requests.exceptions.RequestException as e:
                logger.debug(f"  Poll {attempt}: connection error {e}")
                continue

            # state.current returns PLAIN TEXT, not JSON!
            status = resp.text.strip() if resp.status_code == 200 else ""

            if status != last_status:
                logger.debug(f"  Poll {attempt}: status={status}")
                last_status = status

            if status == "processed":
                logger.info(f"  Job {job_id}: processed ✅")
                return {"status": "processed", "job_id": job_id}
            elif status == "failed":
                # Get details from job.json for error info
                try:
                    detail = self.get_result(job_id)
                    err = detail.get("error", "unknown error")
                except Exception:
                    err = "unknown error"
                raise ProdiaJobFailedError(f"Job {job_id} failed: {err}")
            elif "error" in status.lower() or "validation" in status.lower():
                raise ProdiaValidationError(f"Job {job_id} {status}")

            if attempt > 0 and attempt % 15 == 0:
                logger.info(f"  Still polling ({attempt}/{max_retries}): status={status}")

        raise ProdiaTimeoutError(
            f"Job {job_id} not processed after {max_retries} retries (~{max_retries * initial_delay:.0f}s)"
        )

    # ────────────────────────────────────────────────────────────────────────

    def get_result(self, job_id: str) -> dict:
        """
        ดึง Result + Price จาก Job
        
        GET /v2/job/async/:id/job.json?price=true
        
        Returns:
            dict: {
                "output": { ... },        # ผลลัพธ์ (url, video_url, etc.)
                "state": { ... },
                "price": {
                    "product": "wan2-7",
                    "dollars": 0.03
                },
                "metrics": { "elapsed": 12.5, "ips": None }
            }
        """
        url = f"{self.base_url}/job/async/{job_id}/job.json?price=true"

        logger.info(f"  Fetching result: {job_id}")

        try:
            resp = self._session.get(url, timeout=30)
        except requests.exceptions.RequestException as e:
            raise ProdiaV2Error(f"Failed to fetch result: {e}")

        if resp.status_code != 200:
            raise ProdiaV2Error(f"Get result failed ({resp.status_code}): {resp.text[:300]}")

        try:
            data = resp.json()
        except json.JSONDecodeError:
            raise ProdiaV2Error(f"Result not JSON: {resp.text[:200]}")

        # Log price
        price = data.get("price", {})
        if price:
            logger.info(
                f"  Price: ${price.get('dollars', '?')} "
                f"(product: {price.get('product', '?')})"
            )

        return data

    # ────────────────────────────────────────────────────────────────────────

    def wait_for_result(self, job_id: str, **poll_kwargs) -> dict:
        """
        One-shot: poll → get_result
        
        Args:
            job_id: jobId
            **poll_kwargs: ส่งต่อให้ poll_until_processed()
        
        Returns:
            dict: result from get_result() (รวม price)
        """
        self.poll_until_processed(job_id, **poll_kwargs)
        return self.get_result(job_id)

    # ────────────────────────────────────────────────────────────────────────

    def generate_video(
        self,
        prompt: str,
        input_image: Optional[bytes] = None,
        duration: int = 8,
        resolution: str = "720P",
        ratio: str = "9:16",
        job_type: Optional[str] = None,
        **extra_config,
    ) -> dict:
        """
        Full video gen: create → wait → extract output + price
        
        Returns:
            dict: {
                "job_id": str,
                "output_url": str,
                "price": { "product": str, "dollars": float },
                "metrics": { "elapsed": float, "ips": Optional[float] },
                "result_raw": dict
            }
        """
        if job_type is None:
            job_type = (
                "inference.wan2-7.img2vid.v1"
                if input_image
                else "inference.wan2-7.txt2vid.v1"
            )

        config = {
            "prompt": prompt,
            "duration": duration,
            "resolution": resolution,
            "ratio": ratio,
        }
        config.update(extra_config)

        inputs = [input_image] if input_image else None

        job_id = self.create_job(
            job_type=job_type,
            config=config,
            inputs=inputs,
            accept="video/mp4",
        )

        result = self.wait_for_result(job_id)
        output_url = self._extract_output_url(result, "video")

        return {
            "job_id": job_id,
            "output_url": output_url,
            "price": result.get("price", {}),
            "metrics": result.get("metrics", {}),
            "result_raw": result,
        }

    # ────────────────────────────────────────────────────────────────────────

    def generate_image(
        self,
        prompt: str,
        input_image: Optional[bytes] = None,
        job_type: Optional[str] = None,
        accept: str = "image/png",
        **extra_config,
    ) -> dict:
        """
        Full image gen: create → wait → extract output + price
        
        Returns:
            dict: {
                "job_id": str,
                "output_url": str,
                "price": { "product": str, "dollars": float },
                "metrics": { "elapsed": float },
                "result_raw": dict
            }
        """
        if job_type is None:
            job_type = (
                "inference.nano-banana.img2img.v2"
                if input_image
                else "inference.flux-2.dev.txt2img.v1"
            )

        config = {"prompt": prompt}
        config.update(extra_config)

        inputs = [input_image] if input_image else None

        job_id = self.create_job(
            job_type=job_type,
            config=config,
            inputs=inputs,
            accept=accept,
        )

        result = self.wait_for_result(job_id)
        output_url = self._extract_output_url(result, "image")

        return {
            "job_id": job_id,
            "output_url": output_url,
            "price": result.get("price", {}),
            "metrics": result.get("metrics", {}),
            "result_raw": result,
        }


    # ═══════════════════════════════════════════════════════════════════════
    # Internal helpers
    # ═══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _handle_job_response(resp: requests.Response, job_type: str) -> str:
        """Handle create_job HTTP response → jobId or raise."""
        if resp.status_code in (200, 201):
            try:
                data = resp.json()
            except json.JSONDecodeError:
                raise ProdiaV2Error(f"Non-JSON {resp.status_code} response: {resp.text[:200]}")

            job_id = data.get("id") or data.get("job")
            if job_id:
                logger.info(f"  Job created: {job_id}")
                return job_id
            raise ProdiaV2Error(f"No job ID in {resp.status_code} response: {json.dumps(data)[:200]}")

        if resp.status_code == 400:
            detail = ProdiaV2Client._extract_error(resp)
            raise ProdiaValidationError(f"Config rejected ({job_type}): {detail}")
        elif resp.status_code == 401:
            raise ProdiaV2Error(f"Auth failed (401): check PRODIA_TOKEN")
        elif resp.status_code == 403:
            raise ProdiaV2Error(f"Forbidden (403): {ProdiaV2Client._extract_error(resp)}")
        elif resp.status_code == 429:
            raise ProdiaRateLimitError(f"Rate limited (429)")
        elif resp.status_code >= 500:
            raise ProdiaV2Error(
                f"Prodia server error ({resp.status_code}): "
                f"{ProdiaV2Client._extract_error(resp)}"
            )
        else:
            raise ProdiaV2Error(
                f"Unexpected status ({resp.status_code}): {resp.text[:300]}"
            )

    @staticmethod
    def _extract_error(resp_or_data) -> str:
        """Extract error message from Response or dict."""
        if isinstance(resp_or_data, requests.Response):
            resp = resp_or_data
            try:
                data = resp.json()
            except (json.JSONDecodeError, ValueError):
                return resp.text[:300]
        else:
            data = resp_or_data

        error = data.get("error") or data.get("message") or ""
        if isinstance(error, dict):
            error = json.dumps(error)

        # Check state.history for more details
        state = data.get("state", {})
        if isinstance(state, dict):
            hist = state.get("history", [])
            if hist:
                msg = hist[-1].get("message") or hist[-1].get("error") or ""
                if msg and msg not in str(error):
                    error = f"{error}; {msg}" if error else msg

        return str(error)[:300]

    @staticmethod
    def _extract_output_url(data: dict, media_type: str = "video") -> Optional[str]:
        """Extract output URL from result data (multiple key formats)."""
        output = data.get("output", {})

        # output dict
        if isinstance(output, dict):
            for key in ("url", "video_url", "image_url", "mp4", "outputUrl"):
                val = output.get(key)
                if val:
                    return val

        # output string
        if isinstance(output, str):
            return output

        # output list
        if isinstance(output, list) and output:
            item = output[0]
            if isinstance(item, str):
                return item
            if isinstance(item, dict):
                for key in ("url", "video_url", "image_url", "outputUrl"):
                    val = item.get(key)
                    if val:
                        return val

        # Root-level keys
        for key in ("url", "outputUrl", "video_url", "image_url", "imageUrl"):
            val = data.get(key)
            if val:
                return val

        # state.output
        state = data.get("state", {})
        if isinstance(state, dict):
            so = state.get("output", state.get("result", {}))
            if isinstance(so, dict):
                for key in ("url", "video_url", "image_url"):
                    val = so.get(key)
                    if val:
                        return val

        return None

    @staticmethod
    def format_price_log(price: dict) -> str:
        """Format price dict → log string."""
        product = price.get("product", "?")
        dollars = price.get("dollars", "?")
        credits = price.get("credits", price.get("tokens", "?"))
        return f"${dollars} ({product}) [{credits} credits]"


# ═══════════════════════════════════════════════════════════════════════════
# Convenience: global default client
# ═══════════════════════════════════════════════════════════════════════════

_default_client: Optional[ProdiaV2Client] = None


def get_default_client(token: Optional[str] = None) -> ProdiaV2Client:
    """Get or create default client (lazy init with PRODIA_TOKEN)."""
    global _default_client
    if _default_client is None:
        t = token or os.environ.get("PRODIA_TOKEN", "")
        if not t:
            raise ProdiaV2Error("PRODIA_TOKEN not set")
        _default_client = ProdiaV2Client(t)
    return _default_client


# ═══════════════════════════════════════════════════════════════════════════
# CLI Test
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )

    parser = argparse.ArgumentParser(description="Test Prodia v2 Async API")
    parser.add_argument("--prompt", required=True, help="Prompt")
    parser.add_argument("--type", default="txt2vid",
                        choices=["txt2vid", "img2vid", "txt2img", "img2img"],
                        help="Job type")
    parser.add_argument("--image", help="Input image path")
    parser.add_argument("--duration", type=int, default=8)
    parser.add_argument("--resolution", default="720P")
    parser.add_argument("--ratio", default="9:16")
    args = parser.parse_args()

    type_map = {
        "txt2vid": "inference.wan2-7.txt2vid.v1",
        "img2vid": "inference.wan2-7.img2vid.v1",
        "txt2img": "inference.flux-2.dev.txt2img.v1",
        "img2img": "inference.nano-banana.img2img.v2",
    }
    accept_map = {
        "txt2vid": "video/mp4",
        "img2vid": "video/mp4",
        "txt2img": "image/png",
        "img2img": "image/png",
    }

    job_type = type_map[args.type]
    accept = accept_map[args.type]

    image_bytes = None
    if args.image:
        with open(args.image, "rb") as f:
            image_bytes = f.read()

    print(f"\n🚀 Type: {job_type}")
    print(f"   Prompt: {args.prompt}")
    print(f"   Image: {'Yes' if image_bytes else 'No'}")

    client = ProdiaV2Client(token=os.environ.get("PRODIA_TOKEN", ""))

    try:
        config = {"prompt": args.prompt}
        if args.type in ("txt2vid", "img2vid"):
            config.update(duration=args.duration, resolution=args.resolution, ratio=args.ratio)

        job_id = client.create_job(job_type, config,
                                   inputs=[image_bytes] if image_bytes else None,
                                   accept=accept)
        print(f"   Job ID: {job_id}")

        result = client.wait_for_result(job_id)
        output_url = client._extract_output_url(result)
        price = result.get("price", {})

        print(f"\n✅  Complete!")
        print(f"   Output: {output_url}")
        print(f"   Price : {ProdiaV2Client.format_price_log(price)}")
        print(f"   Metrics: {result.get('metrics', {})}")

    except ProdiaValidationError as e:
        print(f"\n❌ Validation Error: {e}")
    except ProdiaJobFailedError as e:
        print(f"\n❌ Job Failed: {e}")
    except ProdiaTimeoutError as e:
        print(f"\n⏰ Timeout: {e}")
    except ProdiaV2Error as e:
        print(f"\n❌ Error: {e}")
