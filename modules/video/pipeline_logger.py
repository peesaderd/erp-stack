#!/usr/bin/env python3
"""
Pipeline Logger — SQLite-based logging for all pipeline jobs
=============================================================
Tracks every pipeline job with full metadata:
- Input (product info, recipe, UGC style)
- Prompts (image, video, script)
- Files (generated image, TTS, video, final)
- Costs (per step)
- Timing (per step)
- Errors
"""

import sqlite3
import json
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger("pipeline-logger")

# Database path
DB_PATH = Path(__file__).resolve().parent / "storage" / "pipeline_logs.db"


class PipelineLogger:
    """SQLite-based logger for pipeline jobs"""
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema"""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pipeline_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT UNIQUE NOT NULL,
                    run_id TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status TEXT NOT NULL DEFAULT 'running',
                    
                    -- Input
                    product_id TEXT,
                    product_title TEXT,
                    product_image_path TEXT,
                    product_description TEXT,
                    product_price REAL,
                    recipe_name TEXT DEFAULT 'tus',
                    ugc_style TEXT,
                    voice TEXT DEFAULT 'Aoede',
                    
                    -- Analysis
                    product_analysis TEXT,  -- JSON: features, colors, style, category
                    
                    -- Prompts
                    image_prompt TEXT,
                    video_prompts TEXT,     -- JSON array (one per scene)
                    script TEXT,            -- Full TTS script
                    negative_prompt TEXT,
                    hashtags TEXT,          -- JSON array
                    
                    -- Scene structure (from recipe)
                    scenes TEXT,            -- JSON: [{name, duration, function, content}, ...]
                    
                    -- Generated Files
                    generated_image_path TEXT,
                    tts_audio_path TEXT,
                    video_path TEXT,
                    final_video_path TEXT,
                    
                    -- Cost
                    cost_image REAL DEFAULT 0,
                    cost_voice REAL DEFAULT 0,
                    cost_video REAL DEFAULT 0,
                    cost_total REAL DEFAULT 0,
                    
                    -- Timing
                    started_at DATETIME,
                    completed_at DATETIME,
                    duration_analysis_ms INTEGER,
                    duration_image_gen_ms INTEGER,
                    duration_tts_ms INTEGER,
                    duration_video_gen_ms INTEGER,
                    duration_compose_ms INTEGER,
                    duration_total_ms INTEGER,
                    
                    -- v6 timing fields
                    duration_recipe_ms INTEGER DEFAULT 0,
                    duration_script_ms INTEGER DEFAULT 0,
                    duration_image_prompt_ms INTEGER DEFAULT 0,
                    duration_video_prompts_ms INTEGER DEFAULT 0,
                    
                    -- Errors
                    error_message TEXT,
                    error_step TEXT,
                    
                    -- Metadata
                    total_scenes INTEGER,
                    total_duration_seconds REAL,
                    aspect_ratio TEXT DEFAULT '9:16'
                )
            """)
            logger.info(f"Pipeline logger DB initialized: {self.db_path}")
    
    def _connect(self):
        """Get database connection"""
        return sqlite3.connect(str(self.db_path))
    
    def start_job(self, job_id: str, product_info: Dict[str, Any]) -> None:
        """Start a new pipeline job"""
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO pipeline_jobs (
                    job_id, status, started_at,
                    product_id, product_title, product_image_path, 
                    product_description, product_price,
                    recipe_name, ugc_style, voice
                ) VALUES (?, 'running', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id,
                datetime.now().isoformat(),
                product_info.get('product_id', ''),
                product_info.get('product_title', ''),
                product_info.get('product_image', ''),
                product_info.get('product_description', ''),
                product_info.get('product_price', 0.0),
                product_info.get('recipe_name', 'tus'),
                product_info.get('ugc_style', 'holding'),
                product_info.get('voice', 'Aoede'),
            ))
            logger.info(f"Pipeline job started: {job_id}")
    
    def update_analysis(self, job_id: str, analysis: Dict[str, Any]) -> None:
        """Update job with product analysis data"""
        with self._connect() as conn:
            conn.execute("""
                UPDATE pipeline_jobs 
                SET product_analysis = ?, duration_analysis_ms = ?
                WHERE job_id = ?
            """, (
                json.dumps(analysis, ensure_ascii=False),
                analysis.get('duration_ms', 0),
                job_id
            ))
    
    def update_prompts(self, job_id: str, prompts: Dict[str, Any]) -> None:
        """Update job with generated prompts"""
        with self._connect() as conn:
            conn.execute("""
                UPDATE pipeline_jobs 
                SET image_prompt = ?, video_prompts = ?, script = ?, 
                    negative_prompt = ?, hashtags = ?, scenes = ?
                WHERE job_id = ?
            """, (
                prompts.get('image_prompt', ''),
                json.dumps(prompts.get('video_prompts', []), ensure_ascii=False),
                prompts.get('script', ''),
                prompts.get('negative_prompt', ''),
                json.dumps(prompts.get('hashtags', []), ensure_ascii=False),
                json.dumps(prompts.get('scenes', []), ensure_ascii=False),
                job_id
            ))
    
    def update_step(self, job_id: str, step_name: str, data: Dict[str, Any]) -> None:
        """Update a specific step's timing and output"""
        field_map = {
            # v5 steps (backward compat)
            'analysis': ('duration_analysis_ms', None),
            'image_gen': ('duration_image_gen_ms', 'generated_image_path'),
            'tts': ('duration_tts_ms', 'tts_audio_path'),
            'video_gen': ('duration_video_gen_ms', 'video_path'),
            'compose': ('duration_compose_ms', 'final_video_path'),
            
            # v6 steps (new)
            'analyze': ('duration_analysis_ms', None),
            'recipe': ('duration_recipe_ms', None),
            'script': ('duration_script_ms', None),
            'image_prompt': ('duration_image_prompt_ms', None),
            'video_prompts': ('duration_video_prompts_ms', None),
        }
        
        if step_name not in field_map:
            logger.warning(f"Unknown step: {step_name}")
            return
        
        duration_field, path_field = field_map[step_name]
        
        with self._connect() as conn:
            if path_field and 'output_path' in data:
                conn.execute(f"""
                    UPDATE pipeline_jobs 
                    SET {duration_field} = ?, {path_field} = ?
                    WHERE job_id = ?
                """, (data.get('duration_ms', 0), data['output_path'], job_id))
            else:
                conn.execute(f"""
                    UPDATE pipeline_jobs 
                    SET {duration_field} = ?
                    WHERE job_id = ?
                """, (data.get('duration_ms', 0), job_id))
    
    def update_cost(self, job_id: str, cost_type: str, amount: float) -> None:
        """Update cost for a specific step"""
        field_map = {
            'image': 'cost_image',
            'voice': 'cost_voice',
            'video': 'cost_video',
        }
        
        if cost_type not in field_map:
            logger.warning(f"Unknown cost type: {cost_type}")
            return
        
        field = field_map[cost_type]
        
        with self._connect() as conn:
            conn.execute(f"""
                UPDATE pipeline_jobs 
                SET {field} = ?, cost_total = (
                    COALESCE(cost_image, 0) + COALESCE(cost_voice, 0) + COALESCE(cost_video, 0) + ?
                )
                WHERE job_id = ?
            """, (amount, amount, job_id))
    
    def complete_job(self, job_id: str, final_path: str, total_duration_ms: int, 
                     total_video_duration: float = 0, total_scenes: int = 1) -> None:
        """Mark job as completed"""
        with self._connect() as conn:
            conn.execute("""
                UPDATE pipeline_jobs 
                SET status = 'completed', 
                    final_video_path = ?,
                    completed_at = ?,
                    duration_total_ms = ?,
                    total_duration_seconds = ?,
                    total_scenes = ?
                WHERE job_id = ?
            """, (
                final_path,
                datetime.now().isoformat(),
                total_duration_ms,
                total_video_duration,
                total_scenes,
                job_id
            ))
            logger.info(f"Pipeline job completed: {job_id} ({total_duration_ms}ms)")
    
    def fail_job(self, job_id: str, error_msg: str, error_step: str = '') -> None:
        """Mark job as failed"""
        with self._connect() as conn:
            conn.execute("""
                UPDATE pipeline_jobs 
                SET status = 'failed', 
                    error_message = ?, 
                    error_step = ?,
                    completed_at = ?
                WHERE job_id = ?
            """, (
                error_msg,
                error_step,
                datetime.now().isoformat(),
                job_id
            ))
            logger.error(f"Pipeline job failed: {job_id} at {error_step}: {error_msg}")
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get full details of a job"""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM pipeline_jobs WHERE job_id = ?", (job_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    def list_jobs(self, limit: int = 100, status: Optional[str] = None, 
                  days: Optional[int] = None) -> List[Dict[str, Any]]:
        """List recent jobs"""
        query = "SELECT * FROM pipeline_jobs"
        params = []
        conditions = []
        
        if status:
            conditions.append("status = ?")
            params.append(status)
        
        if days:
            conditions.append(f"timestamp >= datetime('now', '-{days} days')")
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_stats(self, days: int = 7) -> Dict[str, Any]:
        """Get aggregate statistics for last N days"""
        with self._connect() as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total_jobs,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                    SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) as running,
                    AVG(cost_total) as avg_cost,
                    SUM(cost_total) as total_cost,
                    AVG(duration_total_ms) as avg_duration_ms,
                    MIN(timestamp) as oldest_job,
                    MAX(timestamp) as newest_job
                FROM pipeline_jobs
                WHERE timestamp >= datetime('now', '-{days} days')
            """)
            row = cursor.fetchone()
            if row:
                return {
                    'total_jobs': row[0] or 0,
                    'completed': row[1] or 0,
                    'failed': row[2] or 0,
                    'running': row[3] or 0,
                    'avg_cost': round(row[4] or 0, 4),
                    'total_cost': round(row[5] or 0, 4),
                    'avg_duration_ms': int(row[6] or 0),
                    'oldest_job': row[7],
                    'newest_job': row[8],
                    'days': days
                }
            return {}
    
    def cleanup_old(self, days: int = 7) -> int:
        """Delete job entries older than N days"""
        with self._connect() as conn:
            cursor = conn.execute("""
                DELETE FROM pipeline_jobs 
                WHERE timestamp < datetime('now', '-{days} days')
                AND status IN ('completed', 'failed')
            """)
            deleted = cursor.rowcount
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} old pipeline jobs (>{days} days)")
            return deleted


# Global instance
_pipeline_logger: Optional[PipelineLogger] = None


def get_pipeline_logger() -> PipelineLogger:
    """Get or create global pipeline logger instance"""
    global _pipeline_logger
    if _pipeline_logger is None:
        _pipeline_logger = PipelineLogger()
    return _pipeline_logger


# Convenience functions
def start_job(job_id: str, product_info: Dict[str, Any]) -> None:
    get_pipeline_logger().start_job(job_id, product_info)


def update_analysis(job_id: str, analysis: Dict[str, Any]) -> None:
    get_pipeline_logger().update_analysis(job_id, analysis)


def update_prompts(job_id: str, prompts: Dict[str, Any]) -> None:
    get_pipeline_logger().update_prompts(job_id, prompts)


def update_step(job_id: str, step_name: str, data: Dict[str, Any]) -> None:
    get_pipeline_logger().update_step(job_id, step_name, data)


def update_cost(job_id: str, cost_type: str, amount: float) -> None:
    get_pipeline_logger().update_cost(job_id, cost_type, amount)


def complete_job(job_id: str, final_path: str, total_duration_ms: int,
                 total_video_duration: float = 0, total_scenes: int = 1) -> None:
    get_pipeline_logger().complete_job(
        job_id, final_path, total_duration_ms, total_video_duration, total_scenes
    )


def fail_job(job_id: str, error_msg: str, error_step: str = '') -> None:
    get_pipeline_logger().fail_job(job_id, error_msg, error_step)


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    return get_pipeline_logger().get_job(job_id)


def list_jobs(limit: int = 100, status: Optional[str] = None, 
              days: Optional[int] = None) -> List[Dict[str, Any]]:
    return get_pipeline_logger().list_jobs(limit, status, days)


def get_stats(days: int = 7) -> Dict[str, Any]:
    return get_pipeline_logger().get_stats(days)


def cleanup_old(days: int = 7) -> int:
    return get_pipeline_logger().cleanup_old(days)


if __name__ == "__main__":
    # Test the logger
    logging.basicConfig(level=logging.INFO)
    
    logger_obj = PipelineLogger()
    
    # Start a test job
    test_job_id = f"test_{int(time.time())}"
    logger_obj.start_job(test_job_id, {
        'product_title': 'Test Product',
        'product_price': 99.0,
        'ugc_style': 'holding'
    })
    
    # Update with prompts
    logger_obj.update_prompts(test_job_id, {
        'image_prompt': 'A beautiful product shot',
        'script': 'Check out this amazing product!',
        'hashtags': ['#test', '#product']
    })
    
    # Complete the job
    logger_obj.complete_job(
        test_job_id, 
        '/path/to/final.mp4',
        total_duration_ms=45000,
        total_video_duration=8.0,
        total_scenes=1
    )
    
    # Get the job
    job = logger_obj.get_job(test_job_id)
    print(f"\nTest job: {job['job_id']} - {job['status']}")
    
    # List jobs
    jobs = logger_obj.list_jobs(limit=5)
    print(f"\nRecent jobs: {len(jobs)}")
    
    # Get stats
    stats = logger_obj.get_stats(days=7)
    print(f"\nStats (7 days): {stats}")
