"""
PostgreSQL checkpoint configuration for LangGraph state persistence.

This module provides database setup and configuration for storing
agent workflow state and enabling recovery mechanisms.
"""

import os
import logging
from typing import Optional
import asyncio
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


class CheckpointDatabase:
    """
    Database manager for LangGraph checkpoints.
    
    Handles database initialization, connection management,
    and checkpoint table creation for state persistence.
    """
    
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or os.getenv(
            "POSTGRES_URL", 
            "postgresql://postgres:password@localhost:5432/ai_calling_agent"
        )
        self.async_database_url = self.database_url.replace("postgresql://", "postgresql+asyncpg://")
        
        self.engine = None
        self.async_engine = None
        self.session_factory = None
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def initialize(self) -> bool:
        """
        Initialize the database connection and create required tables.
        
        Returns:
            True if initialization was successful
        """
        try:
            # Create async engine
            self.async_engine = create_async_engine(
                self.async_database_url,
                echo=False,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True
            )
            
            # Create session factory
            self.session_factory = sessionmaker(
                self.async_engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Test connection
            async with self.async_engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            
            # Create checkpoint tables if they don't exist
            await self._create_checkpoint_tables()
            
            self.logger.info("Database initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            return False
    
    async def _create_checkpoint_tables(self):
        """Create the required tables for LangGraph checkpoints."""
        
        # SQL for creating checkpoint tables
        checkpoint_table_sql = """
        CREATE TABLE IF NOT EXISTS checkpoints (
            thread_id TEXT NOT NULL,
            checkpoint_ns TEXT NOT NULL DEFAULT '',
            checkpoint_id TEXT NOT NULL,
            parent_checkpoint_id TEXT,
            type TEXT,
            checkpoint JSONB NOT NULL,
            metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
        );
        
        CREATE INDEX IF NOT EXISTS idx_checkpoints_thread_id 
        ON checkpoints(thread_id);
        
        CREATE INDEX IF NOT EXISTS idx_checkpoints_created_at 
        ON checkpoints(created_at);
        """
        
        writes_table_sql = """
        CREATE TABLE IF NOT EXISTS checkpoint_writes (
            thread_id TEXT NOT NULL,
            checkpoint_ns TEXT NOT NULL DEFAULT '',
            checkpoint_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            idx INTEGER NOT NULL,
            channel TEXT NOT NULL,
            type TEXT,
            value JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
        );
        
        CREATE INDEX IF NOT EXISTS idx_checkpoint_writes_thread_id 
        ON checkpoint_writes(thread_id);
        """
        
        try:
            async with self.async_engine.begin() as conn:
                await conn.execute(text(checkpoint_table_sql))
                await conn.execute(text(writes_table_sql))
                
            self.logger.info("Checkpoint tables created successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to create checkpoint tables: {e}")
            raise
    
    async def health_check(self) -> bool:
        """
        Check database health and connectivity.
        
        Returns:
            True if database is healthy
        """
        try:
            async with self.async_engine.begin() as conn:
                result = await conn.execute(text("SELECT 1"))
                return result.scalar() == 1
                
        except Exception as e:
            self.logger.error(f"Database health check failed: {e}")
            return False
    
    async def cleanup_old_checkpoints(self, days_to_keep: int = 30):
        """
        Clean up old checkpoint data to manage storage.
        
        Args:
            days_to_keep: Number of days of checkpoint data to retain
        """
        cleanup_sql = """
        DELETE FROM checkpoints 
        WHERE created_at < NOW() - INTERVAL '%s days';
        
        DELETE FROM checkpoint_writes 
        WHERE created_at < NOW() - INTERVAL '%s days';
        """
        
        try:
            async with self.async_engine.begin() as conn:
                result = await conn.execute(text(cleanup_sql % (days_to_keep, days_to_keep)))
                self.logger.info(f"Cleaned up old checkpoints: {result.rowcount} rows deleted")
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup old checkpoints: {e}")
    
    async def get_checkpoint_stats(self) -> dict:
        """
        Get statistics about checkpoint storage.
        
        Returns:
            Dictionary with checkpoint statistics
        """
        stats_sql = """
        SELECT 
            COUNT(*) as total_checkpoints,
            COUNT(DISTINCT thread_id) as unique_workflows,
            MIN(created_at) as oldest_checkpoint,
            MAX(created_at) as newest_checkpoint,
            pg_size_pretty(pg_total_relation_size('checkpoints')) as table_size
        FROM checkpoints;
        """
        
        try:
            async with self.async_engine.begin() as conn:
                result = await conn.execute(text(stats_sql))
                row = result.fetchone()
                
                return {
                    "total_checkpoints": row[0],
                    "unique_workflows": row[1],
                    "oldest_checkpoint": row[2].isoformat() if row[2] else None,
                    "newest_checkpoint": row[3].isoformat() if row[3] else None,
                    "table_size": row[4]
                }
                
        except Exception as e:
            self.logger.error(f"Failed to get checkpoint stats: {e}")
            return {}
    
    async def close(self):
        """Close database connections."""
        if self.async_engine:
            await self.async_engine.dispose()
            self.logger.info("Database connections closed")


class CheckpointManager:
    """
    High-level manager for checkpoint operations.
    
    Provides convenient methods for managing workflow state
    persistence and recovery.
    """
    
    def __init__(self, database: CheckpointDatabase):
        self.database = database
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def save_workflow_state(self, 
                                workflow_id: str, 
                                state: dict, 
                                metadata: dict = None) -> bool:
        """
        Save workflow state as a checkpoint.
        
        Args:
            workflow_id: Workflow identifier
            state: Workflow state to save
            metadata: Additional metadata
            
        Returns:
            True if save was successful
        """
        try:
            # This would integrate with LangGraph's checkpoint system
            # For now, we'll log the operation
            self.logger.info(f"Saving checkpoint for workflow {workflow_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save checkpoint for {workflow_id}: {e}")
            return False
    
    async def load_workflow_state(self, workflow_id: str) -> Optional[dict]:
        """
        Load the latest workflow state from checkpoints.
        
        Args:
            workflow_id: Workflow identifier
            
        Returns:
            Workflow state or None if not found
        """
        try:
            # This would integrate with LangGraph's checkpoint system
            # For now, return None
            self.logger.info(f"Loading checkpoint for workflow {workflow_id}")
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to load checkpoint for {workflow_id}: {e}")
            return None
    
    async def list_workflow_checkpoints(self, workflow_id: str) -> list:
        """
        List all checkpoints for a workflow.
        
        Args:
            workflow_id: Workflow identifier
            
        Returns:
            List of checkpoint information
        """
        checkpoints_sql = """
        SELECT checkpoint_id, parent_checkpoint_id, type, created_at, metadata
        FROM checkpoints 
        WHERE thread_id = %s 
        ORDER BY created_at DESC;
        """
        
        try:
            async with self.database.async_engine.begin() as conn:
                result = await conn.execute(text(checkpoints_sql), (workflow_id,))
                rows = result.fetchall()
                
                return [
                    {
                        "checkpoint_id": row[0],
                        "parent_checkpoint_id": row[1],
                        "type": row[2],
                        "created_at": row[3].isoformat() if row[3] else None,
                        "metadata": row[4]
                    }
                    for row in rows
                ]
                
        except Exception as e:
            self.logger.error(f"Failed to list checkpoints for {workflow_id}: {e}")
            return []
    
    async def recover_workflow(self, workflow_id: str, checkpoint_id: str = None) -> Optional[dict]:
        """
        Recover a workflow from a specific checkpoint.
        
        Args:
            workflow_id: Workflow identifier
            checkpoint_id: Specific checkpoint to recover from (latest if None)
            
        Returns:
            Recovered workflow state
        """
        try:
            if checkpoint_id:
                self.logger.info(f"Recovering workflow {workflow_id} from checkpoint {checkpoint_id}")
            else:
                self.logger.info(f"Recovering workflow {workflow_id} from latest checkpoint")
            
            # This would integrate with LangGraph's recovery system
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to recover workflow {workflow_id}: {e}")
            return None


# Global database instance
checkpoint_db = CheckpointDatabase()
checkpoint_manager = CheckpointManager(checkpoint_db)


async def initialize_checkpoint_system() -> bool:
    """
    Initialize the checkpoint system.
    
    Returns:
        True if initialization was successful
    """
    return await checkpoint_db.initialize()


async def cleanup_checkpoint_system():
    """Clean up the checkpoint system."""
    await checkpoint_db.close()