#!/usr/bin/env python3
"""
Comprehensive Evaluation and Logging System for CAMINA Dataset Expansion
Tracks performance metrics across all models and experiments with detailed logging
"""

import os
import json
import csv
import logging
import argparse
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from collections import defaultdict

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class ExperimentLog:
    """Comprehensive experiment logging structure"""
    experiment_id: str
    timestamp: str
    model_name: str
    dataset_version: str
    
    # Training metrics
    training_time_hrs: float = 0.0
    total_epochs: int = 0
    best_epoch: int = 0
    final_loss: float = 0.0
    
    # Validation metrics  
    map_05: float = 0.0
    map_05_095: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    
    # Per-class performance
    pedestrian_map: float = 0.0
    cyclist_map: float = 0.0
    car_map: float = 0.0
    motorcycle_map: float = 0.0
    bus_map: float = 0.0
    truck_map: float = 0.0
    escooter_map: float = 0.0
    suv_map: float = 0.0
    delivery_van_map: float = 0.0
    
    # Model characteristics
    model_size_mb: float = 0.0
    total_parameters: int = 0
    flops: float = 0.0
    
    # Performance metrics
    video_fps: float = 0.0
    real_world_fps: float = 0.0
    inference_time_ms: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    
    # Hardware info
    device_used: str = ""
    gpu_memory_gb: float = 0.0
    
    # Additional metadata
    batch_size: int = 16
    image_size: int = 640
    optimizer: str = ""
    learning_rate: float = 0.001
    augmentations: str = ""
    notes: str = ""

class ExperimentDatabase:
    """SQLite database for storing experiment results"""
    
    def __init__(self, db_path: str = "experiments.db"):
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(str(self.db_path))
        self.create_tables()
    
    def create_tables(self):
        """Create database tables for experiments"""
        cursor = self.conn.cursor()
        
        # Main experiments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS experiments (
                experiment_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                model_name TEXT NOT NULL,
                dataset_version TEXT,
                training_time_hrs REAL,
                total_epochs INTEGER,
                best_epoch INTEGER,
                final_loss REAL,
                map_05 REAL,
                map_05_095 REAL,
                precision_score REAL,
                recall_score REAL,
                f1_score REAL,
                pedestrian_map REAL,
                cyclist_map REAL,
                car_map REAL,
                motorcycle_map REAL,
                bus_map REAL,
                truck_map REAL,
                escooter_map REAL,
                suv_map REAL,
                delivery_van_map REAL,
                model_size_mb REAL,
                total_parameters INTEGER,
                flops REAL,
                video_fps REAL,
                real_world_fps REAL,
                inference_time_ms REAL,
                memory_usage_mb REAL,
                cpu_usage_percent REAL,
                device_used TEXT,
                gpu_memory_gb REAL,
                batch_size INTEGER,
                image_size INTEGER,
                optimizer TEXT,
                learning_rate REAL,
                augmentations TEXT,
                notes TEXT
            )
        ''')
        
        # Training history table for epoch-by-epoch metrics
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS training_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id TEXT,
                epoch INTEGER,
                train_loss REAL,
                val_loss REAL,
                val_map_05 REAL,
                learning_rate REAL,
                timestamp TEXT,
                FOREIGN KEY (experiment_id) REFERENCES experiments (experiment_id)
            )
        ''')
        
        # Per-class sample counts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS class_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id TEXT,
                class_name TEXT,
                train_samples INTEGER,
                val_samples INTEGER,
                test_samples INTEGER,
                FOREIGN KEY (experiment_id) REFERENCES experiments (experiment_id)
            )
        ''')
        
        self.conn.commit()
    
    def insert_experiment(self, experiment: ExperimentLog):
        """Insert experiment record into database"""
        cursor = self.conn.cursor()
        
        # Convert dataclass to dict and insert
        exp_dict = asdict(experiment)
        columns = ', '.join(exp_dict.keys())
        placeholders = ', '.join(['?' for _ in exp_dict])
        
        cursor.execute(f'''
            INSERT OR REPLACE INTO experiments ({columns})
            VALUES ({placeholders})
        ''', list(exp_dict.values()))
        
        self.conn.commit()
        logger.info(f"Inserted experiment: {experiment.experiment_id}")
    
    def insert_training_epoch(self, experiment_id: str, epoch: int, 
                            train_loss: float, val_loss: float, val_map_05: float, 
                            learning_rate: float):
        """Insert training epoch metrics"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO training_history 
            (experiment_id, epoch, train_loss, val_loss, val_map_05, learning_rate, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (experiment_id, epoch, train_loss, val_loss, val_map_05, 
              learning_rate, datetime.now().isoformat()))
        self.conn.commit()
    
    def get_experiment(self, experiment_id: str) -> Optional[ExperimentLog]:
        """Retrieve experiment by ID"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM experiments WHERE experiment_id = ?', (experiment_id,))
        row = cursor.fetchone()
        
        if row:
            columns = [description[0] for description in cursor.description]
            exp_dict = dict(zip(columns, row))
            return ExperimentLog(**exp_dict)
        return None
    
    def get_all_experiments(self) -> List[ExperimentLog]:
        """Get all experiments"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM experiments ORDER BY timestamp DESC')
        rows = cursor.fetchall()
        
        experiments = []
        columns = [description[0] for description in cursor.description]
        for row in rows:
            exp_dict = dict(zip(columns, row))
            experiments.append(ExperimentLog(**exp_dict))
        
        return experiments
    
    def get_experiments_by_model(self, model_name: str) -> List[ExperimentLog]:
        """Get experiments for specific model"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM experiments WHERE model_name = ? ORDER BY timestamp DESC', 
                      (model_name,))
        rows = cursor.fetchall()
        
        experiments = []
        columns = [description[0] for description in cursor.description]
        for row in rows:
            exp_dict = dict(zip(columns, row))
            experiments.append(ExperimentLog(**exp_dict))
        
        return experiments
    
    def close(self):
        """Close database connection"""
        self.conn.close()

class PerformanceLogger:
    """Advanced performance logging and analysis system"""
    
    def __init__(self, log_dir: str = "logs", db_path: str = "experiments.db"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        self.db = ExperimentDatabase(db_path)
        
        # Set up file logger
        self.file_logger = logging.getLogger('performance')
        handler = logging.FileHandler(self.log_dir / 'performance.log')
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.file_logger.addHandler(handler)
        self.file_logger.setLevel(logging.INFO)
        
        logger.info(f"Performance logger initialized: {self.log_dir}")
    
    def log_experiment_start(self, experiment_id: str, model_name: str, config: Dict):
        """Log experiment start"""
        self.file_logger.info(f"EXPERIMENT_START: {experiment_id} - {model_name}")
        self.file_logger.info(f"CONFIG: {json.dumps(config, indent=2)}")
        
        # Save config to file
        config_file = self.log_dir / f"{experiment_id}_config.json"
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
    
    def log_training_epoch(self, experiment_id: str, epoch: int, metrics: Dict):
        """Log training epoch metrics"""
        self.file_logger.info(f"EPOCH: {experiment_id} - {epoch} - {metrics}")
        
        # Save to database
        self.db.insert_training_epoch(
            experiment_id, epoch,
            metrics.get('train_loss', 0.0),
            metrics.get('val_loss', 0.0),
            metrics.get('val_map_05', 0.0),
            metrics.get('learning_rate', 0.0)
        )
    
    def log_experiment_complete(self, experiment: ExperimentLog):
        """Log experiment completion"""
        self.file_logger.info(f"EXPERIMENT_COMPLETE: {experiment.experiment_id}")
        self.file_logger.info(f"FINAL_METRICS: mAP@0.5={experiment.map_05:.3f}, "
                             f"FPS={experiment.real_world_fps:.1f}, "
                             f"Size={experiment.model_size_mb:.1f}MB")
        
        # Save to database
        self.db.insert_experiment(experiment)
        
        # Save detailed JSON log
        json_file = self.log_dir / f"{experiment.experiment_id}_results.json"
        with open(json_file, 'w') as f:
            json.dump(asdict(experiment), f, indent=2)
    
    def log_performance_metrics(self, experiment_id: str, metrics: Dict):
        """Log detailed performance metrics"""
        self.file_logger.info(f"PERFORMANCE: {experiment_id} - {metrics}")
        
        # Save performance log
        perf_file = self.log_dir / f"{experiment_id}_performance.json"
        with open(perf_file, 'w') as f:
            json.dump(metrics, f, indent=2)
    
    def generate_comparison_report(self, output_file: str = None) -> Dict:
        """Generate comprehensive comparison report"""
        experiments = self.db.get_all_experiments()
        
        if not experiments:
            logger.warning("No experiments found in database")
            return {}
        
        # Convert to DataFrame for analysis
        data = [asdict(exp) for exp in experiments]
        df = pd.DataFrame(data)
        
        # Generate comprehensive analysis
        report = {
            'summary': {
                'total_experiments': len(experiments),
                'models_tested': df['model_name'].nunique(),
                'best_overall_map': df.loc[df['map_05'].idxmax()].to_dict(),
                'fastest_model': df.loc[df['real_world_fps'].idxmax()].to_dict(),
                'smallest_model': df.loc[df['model_size_mb'].idxmin()].to_dict(),
            },
            'model_comparison': self._generate_model_comparison(df),
            'per_class_analysis': self._generate_per_class_analysis(df),
            'performance_trends': self._generate_performance_trends(df),
            'efficiency_analysis': self._generate_efficiency_analysis(df),
            'recommendations': self._generate_recommendations(df)
        }
        
        # Save report
        if output_file is None:
            output_file = self.log_dir / f"comparison_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Comparison report generated: {output_file}")
        return report
    
    def _generate_model_comparison(self, df: pd.DataFrame) -> Dict:
        """Generate model-by-model comparison"""
        model_stats = {}
        
        for model in df['model_name'].unique():
            model_df = df[df['model_name'] == model]
            
            model_stats[model] = {
                'experiments_count': len(model_df),
                'avg_map_05': float(model_df['map_05'].mean()),
                'avg_fps': float(model_df['real_world_fps'].mean()),
                'avg_size_mb': float(model_df['model_size_mb'].mean()),
                'avg_training_time': float(model_df['training_time_hrs'].mean()),
                'best_map_05': float(model_df['map_05'].max()),
                'std_map_05': float(model_df['map_05'].std()) if len(model_df) > 1 else 0.0
            }
        
        return model_stats
    
    def _generate_per_class_analysis(self, df: pd.DataFrame) -> Dict:
        """Analyze per-class performance across models"""
        class_columns = [
            'pedestrian_map', 'cyclist_map', 'car_map', 'motorcycle_map',
            'bus_map', 'truck_map', 'escooter_map', 'suv_map', 'delivery_van_map'
        ]
        
        class_analysis = {}
        for col in class_columns:
            class_name = col.replace('_map', '')
            class_analysis[class_name] = {
                'avg_map': float(df[col].mean()),
                'max_map': float(df[col].max()),
                'min_map': float(df[col].min()),
                'std_map': float(df[col].std()),
                'best_model': df.loc[df[col].idxmax(), 'model_name'] if not df[col].isna().all() else 'N/A'
            }
        
        return class_analysis
    
    def _generate_performance_trends(self, df: pd.DataFrame) -> Dict:
        """Analyze performance trends over time"""
        df['timestamp_dt'] = pd.to_datetime(df['timestamp'])
        df_sorted = df.sort_values('timestamp_dt')
        
        trends = {
            'map_05_trend': {
                'slope': float(np.polyfit(range(len(df_sorted)), df_sorted['map_05'], 1)[0]),
                'improvement_percent': float((df_sorted['map_05'].iloc[-1] - df_sorted['map_05'].iloc[0]) / df_sorted['map_05'].iloc[0] * 100) if len(df_sorted) > 1 else 0.0
            },
            'fps_trend': {
                'slope': float(np.polyfit(range(len(df_sorted)), df_sorted['real_world_fps'], 1)[0]),
                'improvement_percent': float((df_sorted['real_world_fps'].iloc[-1] - df_sorted['real_world_fps'].iloc[0]) / df_sorted['real_world_fps'].iloc[0] * 100) if len(df_sorted) > 1 else 0.0
            },
            'size_trend': {
                'slope': float(np.polyfit(range(len(df_sorted)), df_sorted['model_size_mb'], 1)[0]),
                'reduction_percent': float((df_sorted['model_size_mb'].iloc[0] - df_sorted['model_size_mb'].iloc[-1]) / df_sorted['model_size_mb'].iloc[0] * 100) if len(df_sorted) > 1 else 0.0
            }
        }
        
        return trends
    
    def _generate_efficiency_analysis(self, df: pd.DataFrame) -> Dict:
        """Analyze efficiency metrics (accuracy vs speed vs size)"""
        # Calculate efficiency scores
        df['accuracy_score'] = df['map_05'] / df['map_05'].max()
        df['speed_score'] = df['real_world_fps'] / df['real_world_fps'].max()
        df['size_score'] = df['model_size_mb'].min() / df['model_size_mb']  # Smaller is better
        
        df['efficiency_score'] = (df['accuracy_score'] + df['speed_score'] + df['size_score']) / 3
        
        best_efficiency_idx = df['efficiency_score'].idxmax()
        
        efficiency_analysis = {
            'best_efficiency_model': {
                'model_name': df.loc[best_efficiency_idx, 'model_name'],
                'experiment_id': df.loc[best_efficiency_idx, 'experiment_id'],
                'efficiency_score': float(df.loc[best_efficiency_idx, 'efficiency_score']),
                'accuracy_score': float(df.loc[best_efficiency_idx, 'accuracy_score']),
                'speed_score': float(df.loc[best_efficiency_idx, 'speed_score']),
                'size_score': float(df.loc[best_efficiency_idx, 'size_score'])
            },
            'pareto_frontier': self._find_pareto_frontier(df),
            'trade_offs': {
                'accuracy_vs_speed': float(df['map_05'].corr(df['real_world_fps'])),
                'accuracy_vs_size': float(df['map_05'].corr(df['model_size_mb'])),
                'speed_vs_size': float(df['real_world_fps'].corr(df['model_size_mb']))
            }
        }
        
        return efficiency_analysis
    
    def _find_pareto_frontier(self, df: pd.DataFrame) -> List[Dict]:
        """Find Pareto frontier for multi-objective optimization"""
        pareto_points = []
        
        for i, row1 in df.iterrows():
            is_pareto = True
            for j, row2 in df.iterrows():
                if i != j:
                    # Check if row2 dominates row1
                    if (row2['map_05'] >= row1['map_05'] and 
                        row2['real_world_fps'] >= row1['real_world_fps'] and
                        row2['model_size_mb'] <= row1['model_size_mb'] and
                        (row2['map_05'] > row1['map_05'] or 
                         row2['real_world_fps'] > row1['real_world_fps'] or
                         row2['model_size_mb'] < row1['model_size_mb'])):
                        is_pareto = False
                        break
            
            if is_pareto:
                pareto_points.append({
                    'experiment_id': row1['experiment_id'],
                    'model_name': row1['model_name'],
                    'map_05': float(row1['map_05']),
                    'fps': float(row1['real_world_fps']),
                    'size_mb': float(row1['model_size_mb'])
                })
        
        return pareto_points
    
    def _generate_recommendations(self, df: pd.DataFrame) -> Dict:
        """Generate actionable recommendations based on analysis"""
        recommendations = {
            'for_accuracy': {
                'model': df.loc[df['map_05'].idxmax(), 'model_name'],
                'reason': f"Highest mAP@0.5: {df['map_05'].max():.3f}",
                'trade_offs': f"Speed: {df.loc[df['map_05'].idxmax(), 'real_world_fps']:.1f} FPS, Size: {df.loc[df['map_05'].idxmax(), 'model_size_mb']:.1f}MB"
            },
            'for_speed': {
                'model': df.loc[df['real_world_fps'].idxmax(), 'model_name'],
                'reason': f"Highest FPS: {df['real_world_fps'].max():.1f}",
                'trade_offs': f"Accuracy: {df.loc[df['real_world_fps'].idxmax(), 'map_05']:.3f} mAP, Size: {df.loc[df['real_world_fps'].idxmax(), 'model_size_mb']:.1f}MB"
            },
            'for_deployment': {
                'model': df.loc[df['model_size_mb'].idxmin(), 'model_name'],
                'reason': f"Smallest size: {df['model_size_mb'].min():.1f}MB",
                'trade_offs': f"Accuracy: {df.loc[df['model_size_mb'].idxmin(), 'map_05']:.3f} mAP, Speed: {df.loc[df['model_size_mb'].idxmin(), 'real_world_fps']:.1f} FPS"
            },
            'balanced': {
                'model': df.loc[df['efficiency_score'].idxmax(), 'model_name'] if 'efficiency_score' in df.columns else 'N/A',
                'reason': "Best overall efficiency score",
                'metrics': f"mAP: {df.loc[df['efficiency_score'].idxmax(), 'map_05']:.3f}, FPS: {df.loc[df['efficiency_score'].idxmax(), 'real_world_fps']:.1f}, Size: {df.loc[df['efficiency_score'].idxmax(), 'model_size_mb']:.1f}MB" if 'efficiency_score' in df.columns else 'N/A'
            }
        }
        
        return recommendations
    
    def create_visualization_dashboard(self, output_dir: str = "visualizations"):
        """Create comprehensive visualization dashboard"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        experiments = self.db.get_all_experiments()
        if not experiments:
            logger.warning("No experiments found for visualization")
            return
        
        df = pd.DataFrame([asdict(exp) for exp in experiments])
        
        # Set style
        plt.style.use('seaborn-v0_8')
        sns.set_palette("husl")
        
        # 1. Model Comparison Plot
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        
        # mAP comparison
        df.groupby('model_name')['map_05'].mean().plot(kind='bar', ax=axes[0,0])
        axes[0,0].set_title('Average mAP@0.5 by Model')
        axes[0,0].set_ylabel('mAP@0.5')
        
        # FPS comparison
        df.groupby('model_name')['real_world_fps'].mean().plot(kind='bar', ax=axes[0,1])
        axes[0,1].set_title('Average FPS by Model')
        axes[0,1].set_ylabel('FPS')
        
        # Model size comparison
        df.groupby('model_name')['model_size_mb'].mean().plot(kind='bar', ax=axes[1,0])
        axes[1,0].set_title('Average Model Size by Model')
        axes[1,0].set_ylabel('Size (MB)')
        
        # Training time comparison
        df.groupby('model_name')['training_time_hrs'].mean().plot(kind='bar', ax=axes[1,1])
        axes[1,1].set_title('Average Training Time by Model')
        axes[1,1].set_ylabel('Time (hours)')
        
        plt.tight_layout()
        plt.savefig(output_path / 'model_comparison.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        # 2. Per-class Performance Heatmap
        class_columns = ['pedestrian_map', 'cyclist_map', 'car_map', 'motorcycle_map',
                        'bus_map', 'truck_map', 'escooter_map', 'suv_map', 'delivery_van_map']
        
        class_data = df.groupby('model_name')[class_columns].mean()
        class_data.columns = [col.replace('_map', '').title() for col in class_data.columns]
        
        plt.figure(figsize=(12, 8))
        sns.heatmap(class_data, annot=True, cmap='YlOrRd', fmt='.3f')
        plt.title('Per-Class mAP Performance by Model')
        plt.ylabel('Model')
        plt.xlabel('Class')
        plt.tight_layout()
        plt.savefig(output_path / 'per_class_heatmap.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        # 3. Efficiency Scatter Plot
        plt.figure(figsize=(10, 8))
        for model in df['model_name'].unique():
            model_data = df[df['model_name'] == model]
            plt.scatter(model_data['real_world_fps'], model_data['map_05'], 
                       s=model_data['model_size_mb']*5, alpha=0.7, label=model)
        
        plt.xlabel('Real-world FPS')
        plt.ylabel('mAP@0.5')
        plt.title('Model Efficiency (Size shown by bubble size)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_path / 'efficiency_scatter.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        # 4. Performance Timeline
        if len(df) > 1:
            df['timestamp_dt'] = pd.to_datetime(df['timestamp'])
            df_sorted = df.sort_values('timestamp_dt')
            
            fig, ax = plt.subplots(figsize=(12, 6))
            ax.plot(df_sorted['timestamp_dt'], df_sorted['map_05'], marker='o', label='mAP@0.5')
            ax2 = ax.twinx()
            ax2.plot(df_sorted['timestamp_dt'], df_sorted['real_world_fps'], 
                    marker='s', color='orange', label='FPS')
            
            ax.set_xlabel('Experiment Date')
            ax.set_ylabel('mAP@0.5', color='blue')
            ax2.set_ylabel('FPS', color='orange')
            ax.set_title('Performance Evolution Over Time')
            
            # Combine legends
            lines1, labels1 = ax.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
            
            plt.tight_layout()
            plt.savefig(output_path / 'performance_timeline.png', dpi=300, bbox_inches='tight')
            plt.close()
        
        logger.info(f"Visualization dashboard created: {output_path}")
    
    def export_results_csv(self, output_file: str = None) -> str:
        """Export all results to CSV format"""
        experiments = self.db.get_all_experiments()
        
        if not experiments:
            logger.warning("No experiments found for export")
            return ""
        
        df = pd.DataFrame([asdict(exp) for exp in experiments])
        
        if output_file is None:
            output_file = self.log_dir / f"experiments_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        df.to_csv(output_file, index=False)
        logger.info(f"Results exported to CSV: {output_file}")
        
        return str(output_file)
    
    def cleanup_old_logs(self, days_to_keep: int = 30):
        """Clean up old log files"""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        for file_path in self.log_dir.glob("*.log"):
            if file_path.stat().st_mtime < cutoff_date.timestamp():
                file_path.unlink()
                logger.info(f"Removed old log file: {file_path}")
    
    def close(self):
        """Close database connection"""
        self.db.close()

def main():
    parser = argparse.ArgumentParser(description='CAMINA Evaluation and Logging System')
    parser.add_argument('--action', choices=['report', 'export', 'visualize', 'cleanup'], 
                       default='report', help='Action to perform')
    parser.add_argument('--db-path', default='experiments.db', help='Database path')
    parser.add_argument('--log-dir', default='logs', help='Log directory')
    parser.add_argument('--output', help='Output file/directory')
    parser.add_argument('--days-to-keep', type=int, default=30, 
                       help='Days to keep old logs (for cleanup)')
    
    args = parser.parse_args()
    
    # Initialize logger
    logger_system = PerformanceLogger(args.log_dir, args.db_path)
    
    try:
        if args.action == 'report':
            report = logger_system.generate_comparison_report(args.output)
            print("\n=== COMPARISON REPORT SUMMARY ===")
            print(f"Total Experiments: {report['summary']['total_experiments']}")
            print(f"Models Tested: {report['summary']['models_tested']}")
            print(f"Best Model (mAP): {report['summary']['best_overall_map']['model_name']} "
                  f"({report['summary']['best_overall_map']['map_05']:.3f})")
            print(f"Fastest Model: {report['summary']['fastest_model']['model_name']} "
                  f"({report['summary']['fastest_model']['real_world_fps']:.1f} FPS)")
            print("="*50)
            
        elif args.action == 'export':
            csv_file = logger_system.export_results_csv(args.output)
            print(f"Results exported to: {csv_file}")
            
        elif args.action == 'visualize':
            output_dir = args.output or 'visualizations'
            logger_system.create_visualization_dashboard(output_dir)
            print(f"Visualizations created in: {output_dir}")
            
        elif args.action == 'cleanup':
            logger_system.cleanup_old_logs(args.days_to_keep)
            print(f"Cleaned up logs older than {args.days_to_keep} days")
            
    finally:
        logger_system.close()

if __name__ == '__main__':
    main()