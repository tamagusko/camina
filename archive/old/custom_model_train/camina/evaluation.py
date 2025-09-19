"""
Evaluation and reporting system for CAMINA pipeline.
Comprehensive analysis and report generation for research reproducibility.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from datetime import datetime
import yaml

from .config import CaminaConfig
from .utils import save_json, load_json, format_duration

logger = logging.getLogger(__name__)


class ResultsManager:
    """
    Comprehensive results management and analysis for CAMINA pipeline.
    Handles experiment tracking, metrics analysis, and report generation.
    """
    
    def __init__(self, config: CaminaConfig, results_dir: Union[str, Path] = "results"):
        self.config = config
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize results database
        self.experiments = {}
        self.reports = {}
        
        # Set matplotlib backend for headless environments
        plt.switch_backend('Agg')
        
        logger.info(f"ResultsManager initialized: {self.results_dir}")
    
    def load_experiment(self, experiment_path: Union[str, Path]) -> Optional[Dict[str, Any]]:
        """
        Load experiment results from directory.
        
        Args:
            experiment_path: Path to experiment directory
        
        Returns:
            Experiment data dictionary
        """
        experiment_path = Path(experiment_path)
        
        if not experiment_path.exists():
            logger.error(f"Experiment path not found: {experiment_path}")
            return None
        
        experiment_data = {
            'experiment_id': experiment_path.name,
            'experiment_path': str(experiment_path),
            'loaded_at': datetime.now().isoformat()
        }
        
        # Load training configuration
        config_file = experiment_path / 'training_config.json'
        if config_file.exists():
            experiment_data['training_config'] = load_json(config_file)
        
        # Load training results
        results_file = experiment_path / 'training_results.json'
        if results_file.exists():
            experiment_data['training_results'] = load_json(results_file)
        
        # Load validation results
        validation_file = experiment_path / 'validation_results.json'
        if validation_file.exists():
            experiment_data['validation_results'] = load_json(validation_file)
        
        # Load export results
        export_file = experiment_path / 'export_results.json'
        if export_file.exists():
            experiment_data['export_results'] = load_json(export_file)
        
        # Load training metrics from CSV if available
        results_csv = experiment_path / 'results.csv'
        if results_csv.exists():
            try:
                metrics_df = pd.read_csv(results_csv)
                experiment_data['training_metrics'] = metrics_df.to_dict('records')
            except Exception as e:
                logger.warning(f"Failed to load training metrics CSV: {e}")
        
        # Store experiment
        experiment_id = experiment_data['experiment_id']
        self.experiments[experiment_id] = experiment_data
        
        logger.info(f"Experiment loaded: {experiment_id}")
        return experiment_data
    
    def load_experiments_batch(self, experiments_dir: Union[str, Path]) -> Dict[str, Dict]:
        """
        Load multiple experiments from directory.
        
        Args:
            experiments_dir: Directory containing experiment subdirectories
        
        Returns:
            Dictionary of experiment data
        """
        experiments_dir = Path(experiments_dir)
        
        if not experiments_dir.exists():
            logger.error(f"Experiments directory not found: {experiments_dir}")
            return {}
        
        loaded_experiments = {}
        
        # Find experiment directories
        for exp_dir in experiments_dir.iterdir():
            if exp_dir.is_dir() and (exp_dir / 'training_results.json').exists():
                experiment_data = self.load_experiment(exp_dir)
                if experiment_data:
                    loaded_experiments[experiment_data['experiment_id']] = experiment_data
        
        logger.info(f"Loaded {len(loaded_experiments)} experiments from {experiments_dir}")
        return loaded_experiments
    
    def analyze_training_metrics(self, experiment_id: str) -> Dict[str, Any]:
        """
        Analyze training metrics for an experiment.
        
        Args:
            experiment_id: Experiment identifier
        
        Returns:
            Training metrics analysis
        """
        if experiment_id not in self.experiments:
            logger.error(f"Experiment not found: {experiment_id}")
            return {}
        
        experiment = self.experiments[experiment_id]
        analysis = {
            'experiment_id': experiment_id,
            'analysis_timestamp': datetime.now().isoformat()
        }
        
        # Basic training information
        if 'training_results' in experiment:
            training_results = experiment['training_results']
            analysis['training_summary'] = {
                'success': training_results.get('success', False),
                'training_time_hours': training_results.get('training_time_seconds', 0) / 3600,
                'best_fitness': training_results.get('model_info', {}).get('best_fitness', 0),
                'best_epoch': training_results.get('model_info', {}).get('best_epoch', 0),
                'model_size_mb': training_results.get('model_info', {}).get('model_size_mb', 0)
            }
        
        # Validation metrics
        if 'validation_results' in experiment:
            val_results = experiment['validation_results']
            if val_results.get('success'):
                analysis['validation_metrics'] = val_results.get('metrics', {})
        
        # Training curve analysis
        if 'training_metrics' in experiment:
            metrics = experiment['training_metrics']
            if metrics:
                df = pd.DataFrame(metrics)
                
                # Calculate convergence metrics
                if 'fitness' in df.columns:
                    fitness_values = df['fitness'].dropna()
                    if len(fitness_values) > 0:
                        analysis['convergence'] = {
                            'final_fitness': float(fitness_values.iloc[-1]),
                            'max_fitness': float(fitness_values.max()),
                            'fitness_improvement': float(fitness_values.iloc[-1] - fitness_values.iloc[0]) if len(fitness_values) > 1 else 0,
                            'convergence_epoch': int(fitness_values.idxmax()) if len(fitness_values) > 0 else 0
                        }
                
                # Loss analysis
                loss_columns = [col for col in df.columns if 'loss' in col.lower()]
                if loss_columns:
                    loss_analysis = {}
                    for loss_col in loss_columns:
                        loss_values = df[loss_col].dropna()
                        if len(loss_values) > 0:
                            loss_analysis[loss_col] = {
                                'initial': float(loss_values.iloc[0]),
                                'final': float(loss_values.iloc[-1]),
                                'min': float(loss_values.min()),
                                'reduction': float(loss_values.iloc[0] - loss_values.iloc[-1]) if len(loss_values) > 1 else 0
                            }
                    analysis['loss_analysis'] = loss_analysis
        
        return analysis
    
    def compare_experiments(self, experiment_ids: List[str]) -> Dict[str, Any]:
        """
        Compare multiple experiments.
        
        Args:
            experiment_ids: List of experiment identifiers
        
        Returns:
            Experiment comparison results
        """
        if not experiment_ids:
            return {'error': 'No experiments specified'}
        
        # Filter valid experiments
        valid_experiments = []
        for exp_id in experiment_ids:
            if exp_id in self.experiments:
                valid_experiments.append(exp_id)
            else:
                logger.warning(f"Experiment not found: {exp_id}")
        
        if not valid_experiments:
            return {'error': 'No valid experiments found'}
        
        comparison = {
            'comparison_timestamp': datetime.now().isoformat(),
            'experiments_compared': valid_experiments,
            'metrics_comparison': {},
            'rankings': {}
        }
        
        # Extract metrics for comparison
        metrics_data = []
        for exp_id in valid_experiments:
            experiment = self.experiments[exp_id]
            
            # Get validation metrics
            metrics_row = {'experiment_id': exp_id}
            
            if 'validation_results' in experiment:
                val_metrics = experiment['validation_results'].get('metrics', {})
                metrics_row.update(val_metrics)
            
            if 'training_results' in experiment:
                training_info = experiment['training_results'].get('model_info', {})
                metrics_row.update({
                    'best_fitness': training_info.get('best_fitness', 0),
                    'model_size_mb': training_info.get('model_size_mb', 0),
                    'training_time_hours': experiment['training_results'].get('training_time_seconds', 0) / 3600
                })
            
            metrics_data.append(metrics_row)
        
        # Create comparison DataFrame
        df = pd.DataFrame(metrics_data)
        
        # Calculate rankings
        ranking_metrics = ['map50_95', 'map50', 'f1_score', 'precision', 'recall']
        rankings = {}
        
        for metric in ranking_metrics:
            if metric in df.columns:
                # Rank by descending order (higher is better)
                df[f'{metric}_rank'] = df[metric].rank(ascending=False)
                rankings[metric] = df[['experiment_id', metric, f'{metric}_rank']].sort_values(f'{metric}_rank').to_dict('records')
        
        comparison['metrics_comparison'] = df.to_dict('records')
        comparison['rankings'] = rankings
        
        # Overall ranking (average of individual rankings)
        if ranking_metrics:
            rank_columns = [f'{metric}_rank' for metric in ranking_metrics if f'{metric}_rank' in df.columns]
            if rank_columns:
                df['overall_rank'] = df[rank_columns].mean(axis=1)
                comparison['overall_ranking'] = df[['experiment_id', 'overall_rank']].sort_values('overall_rank').to_dict('records')
        
        return comparison
    
    def create_training_plots(self, experiment_id: str, output_dir: Optional[Union[str, Path]] = None) -> Dict[str, str]:
        """
        Create training visualization plots.
        
        Args:
            experiment_id: Experiment identifier
            output_dir: Directory to save plots (uses results_dir if None)
        
        Returns:
            Dictionary mapping plot names to file paths
        """
        if experiment_id not in self.experiments:
            logger.error(f"Experiment not found: {experiment_id}")
            return {}
        
        experiment = self.experiments[experiment_id]
        
        if output_dir is None:
            output_dir = self.results_dir / 'plots' / experiment_id
        else:
            output_dir = Path(output_dir)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        plot_files = {}
        
        # Training metrics plots
        if 'training_metrics' in experiment:
            metrics_df = pd.DataFrame(experiment['training_metrics'])
            
            if not metrics_df.empty:
                # Loss curves
                loss_columns = [col for col in metrics_df.columns if 'loss' in col.lower()]
                if loss_columns:
                    plt.figure(figsize=(12, 8))
                    for col in loss_columns:
                        if col in metrics_df.columns:
                            plt.plot(metrics_df.index, metrics_df[col], label=col)
                    
                    plt.xlabel('Epoch')
                    plt.ylabel('Loss')
                    plt.title(f'Training Loss Curves - {experiment_id}')
                    plt.legend()
                    plt.grid(True)
                    
                    loss_plot_path = output_dir / 'loss_curves.png'
                    plt.savefig(loss_plot_path, dpi=300, bbox_inches='tight')
                    plt.close()
                    plot_files['loss_curves'] = str(loss_plot_path)
                
                # Metrics curves (mAP, precision, recall)
                metric_columns = [col for col in metrics_df.columns 
                                if any(metric in col.lower() for metric in ['map', 'precision', 'recall', 'f1'])]
                
                if metric_columns:
                    plt.figure(figsize=(12, 8))
                    for col in metric_columns:
                        if col in metrics_df.columns:
                            plt.plot(metrics_df.index, metrics_df[col], label=col)
                    
                    plt.xlabel('Epoch')
                    plt.ylabel('Metric Value')
                    plt.title(f'Training Metrics - {experiment_id}')
                    plt.legend()
                    plt.grid(True)
                    
                    metrics_plot_path = output_dir / 'training_metrics.png'
                    plt.savefig(metrics_plot_path, dpi=300, bbox_inches='tight')
                    plt.close()
                    plot_files['training_metrics'] = str(metrics_plot_path)
        
        logger.info(f"Created {len(plot_files)} plots for {experiment_id}")
        return plot_files
    
    def create_comparison_plots(self, experiment_ids: List[str], output_dir: Optional[Union[str, Path]] = None) -> Dict[str, str]:
        """
        Create comparison plots for multiple experiments.
        
        Args:
            experiment_ids: List of experiment identifiers
            output_dir: Directory to save plots
        
        Returns:
            Dictionary mapping plot names to file paths
        """
        comparison_data = self.compare_experiments(experiment_ids)
        
        if 'error' in comparison_data:
            logger.error(f"Comparison failed: {comparison_data['error']}")
            return {}
        
        if output_dir is None:
            output_dir = self.results_dir / 'plots' / 'comparisons'
        else:
            output_dir = Path(output_dir)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        plot_files = {}
        
        # Metrics comparison bar plot
        metrics_df = pd.DataFrame(comparison_data['metrics_comparison'])
        
        if not metrics_df.empty:
            # Select key metrics for visualization
            key_metrics = ['map50_95', 'map50', 'precision', 'recall', 'f1_score']
            available_metrics = [m for m in key_metrics if m in metrics_df.columns]
            
            if available_metrics:
                fig, axes = plt.subplots(len(available_metrics), 1, figsize=(12, 4*len(available_metrics)))
                if len(available_metrics) == 1:
                    axes = [axes]
                
                for i, metric in enumerate(available_metrics):
                    ax = axes[i]
                    bars = ax.bar(metrics_df['experiment_id'], metrics_df[metric])
                    ax.set_title(f'{metric.upper()} Comparison')
                    ax.set_ylabel(metric)
                    ax.tick_params(axis='x', rotation=45)
                    
                    # Add value labels on bars
                    for bar, value in zip(bars, metrics_df[metric]):
                        if pd.notna(value):
                            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.001,
                                  f'{value:.3f}', ha='center', va='bottom')
                
                plt.tight_layout()
                
                comparison_plot_path = output_dir / 'metrics_comparison.png'
                plt.savefig(comparison_plot_path, dpi=300, bbox_inches='tight')
                plt.close()
                plot_files['metrics_comparison'] = str(comparison_plot_path)
        
        # Training time vs performance scatter plot
        if 'training_time_hours' in metrics_df.columns and 'map50_95' in metrics_df.columns:
            plt.figure(figsize=(10, 8))
            scatter = plt.scatter(metrics_df['training_time_hours'], metrics_df['map50_95'], 
                                s=100, alpha=0.7)
            
            # Add experiment labels
            for i, exp_id in enumerate(metrics_df['experiment_id']):
                plt.annotate(exp_id, (metrics_df['training_time_hours'].iloc[i], 
                                    metrics_df['map50_95'].iloc[i]),
                           xytext=(5, 5), textcoords='offset points')
            
            plt.xlabel('Training Time (hours)')
            plt.ylabel('mAP@0.5:0.95')
            plt.title('Training Time vs Performance')
            plt.grid(True, alpha=0.3)
            
            scatter_plot_path = output_dir / 'time_vs_performance.png'
            plt.savefig(scatter_plot_path, dpi=300, bbox_inches='tight')
            plt.close()
            plot_files['time_vs_performance'] = str(scatter_plot_path)
        
        logger.info(f"Created {len(plot_files)} comparison plots")
        return plot_files
    
    def generate_comprehensive_report(self, 
                                    experiment_ids: Optional[List[str]] = None,
                                    output_file: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """
        Generate comprehensive analysis report.
        
        Args:
            experiment_ids: List of experiments to include (all if None)
            output_file: Path to save report JSON
        
        Returns:
            Comprehensive report dictionary
        """
        # Use all experiments if none specified
        if experiment_ids is None:
            experiment_ids = list(self.experiments.keys())
        
        # Filter valid experiments
        valid_experiments = [exp_id for exp_id in experiment_ids if exp_id in self.experiments]
        
        if not valid_experiments:
            logger.error("No valid experiments found for report generation")
            return {'error': 'No valid experiments'}
        
        logger.info(f"Generating comprehensive report for {len(valid_experiments)} experiments")
        
        report = {
            'report_metadata': {
                'generated_at': datetime.now().isoformat(),
                'generator': 'CAMINA ResultsManager',
                'version': '2.0.0',
                'experiments_included': valid_experiments
            },
            'dataset_info': {
                'classes': self.config.class_schema.CLASSES,
                'num_classes': self.config.class_schema.num_classes,
                'new_classes': [self.config.class_schema.CLASSES[i] for i in self.config.class_schema.NEW_CLASSES]
            }
        }
        
        # Individual experiment analyses
        report['experiment_analyses'] = {}
        for exp_id in valid_experiments:
            analysis = self.analyze_training_metrics(exp_id)
            report['experiment_analyses'][exp_id] = analysis
        
        # Comparative analysis
        if len(valid_experiments) > 1:
            comparison = self.compare_experiments(valid_experiments)
            report['comparative_analysis'] = comparison
        
        # Summary statistics
        report['summary_statistics'] = self._calculate_summary_statistics(valid_experiments)
        
        # Recommendations
        report['recommendations'] = self._generate_recommendations(valid_experiments)
        
        # Save report
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.results_dir / f'camina_comprehensive_report_{timestamp}.json'
        else:
            output_file = Path(output_file)
        
        output_file.parent.mkdir(parents=True, exist_ok=True)
        save_json(report, output_file)
        
        logger.info(f"Comprehensive report saved: {output_file}")
        return report
    
    def _calculate_summary_statistics(self, experiment_ids: List[str]) -> Dict[str, Any]:
        """Calculate summary statistics across experiments"""
        metrics_data = []
        
        for exp_id in experiment_ids:
            experiment = self.experiments[exp_id]
            
            metrics = {}
            if 'validation_results' in experiment:
                val_metrics = experiment['validation_results'].get('metrics', {})
                metrics.update(val_metrics)
            
            if 'training_results' in experiment:
                training_info = experiment['training_results'].get('model_info', {})
                metrics.update({
                    'best_fitness': training_info.get('best_fitness', 0),
                    'model_size_mb': training_info.get('model_size_mb', 0),
                    'training_time_hours': experiment['training_results'].get('training_time_seconds', 0) / 3600
                })
            
            if metrics:
                metrics_data.append(metrics)
        
        if not metrics_data:
            return {}
        
        df = pd.DataFrame(metrics_data)
        
        # Calculate statistics
        summary = {}
        for column in df.columns:
            if df[column].dtype in ['float64', 'int64']:
                summary[column] = {
                    'mean': float(df[column].mean()),
                    'std': float(df[column].std()),
                    'min': float(df[column].min()),
                    'max': float(df[column].max()),
                    'median': float(df[column].median())
                }
        
        return summary
    
    def _generate_recommendations(self, experiment_ids: List[str]) -> List[str]:
        """Generate recommendations based on experiment results"""
        recommendations = []
        
        # Analyze experiment results
        best_experiment = None
        best_map = 0
        
        training_times = []
        model_sizes = []
        
        for exp_id in experiment_ids:
            experiment = self.experiments[exp_id]
            
            # Find best performing experiment
            if 'validation_results' in experiment:
                val_metrics = experiment['validation_results'].get('metrics', {})
                map_score = val_metrics.get('map50_95', 0)
                if map_score > best_map:
                    best_map = map_score
                    best_experiment = exp_id
            
            # Collect training times and model sizes
            if 'training_results' in experiment:
                training_time = experiment['training_results'].get('training_time_seconds', 0) / 3600
                training_times.append(training_time)
                
                model_size = experiment['training_results'].get('model_info', {}).get('model_size_mb', 0)
                model_sizes.append(model_size)
        
        # Generate recommendations
        if best_experiment:
            recommendations.append(f"Best performing model: {best_experiment} with mAP@0.5:0.95 of {best_map:.4f}")
        
        if training_times:
            avg_training_time = np.mean(training_times)
            if avg_training_time > 6:  # More than 6 hours
                recommendations.append("Consider using a smaller batch size or fewer epochs to reduce training time")
            elif avg_training_time < 1:  # Less than 1 hour
                recommendations.append("Training time is very short - consider increasing epochs for better convergence")
        
        if model_sizes:
            avg_model_size = np.mean(model_sizes)
            if avg_model_size > 20:  # More than 20MB
                recommendations.append("Model size is large - consider model pruning or quantization for deployment")
        
        if best_map < 0.5:
            recommendations.append("Low mAP scores detected - consider data augmentation or hyperparameter tuning")
        elif best_map > 0.8:
            recommendations.append("Excellent performance achieved - model ready for deployment")
        
        # Add general recommendations
        recommendations.append("Ensure consistent validation across different lighting and weather conditions")
        recommendations.append("Test model performance on edge cases and rare object configurations")
        recommendations.append("Consider ensemble methods or model averaging for improved robustness")
        
        return recommendations
    
    def export_results_csv(self, 
                          experiment_ids: Optional[List[str]] = None,
                          output_file: Optional[Union[str, Path]] = None) -> str:
        """
        Export experiment results to CSV format.
        
        Args:
            experiment_ids: List of experiments to export
            output_file: Path to save CSV file
        
        Returns:
            Path to saved CSV file
        """
        if experiment_ids is None:
            experiment_ids = list(self.experiments.keys())
        
        # Collect experiment data
        rows = []
        for exp_id in experiment_ids:
            if exp_id not in self.experiments:
                continue
            
            experiment = self.experiments[exp_id]
            row = {'experiment_id': exp_id}
            
            # Add validation metrics
            if 'validation_results' in experiment:
                val_metrics = experiment['validation_results'].get('metrics', {})
                row.update(val_metrics)
            
            # Add training information
            if 'training_results' in experiment:
                training_results = experiment['training_results']
                model_info = training_results.get('model_info', {})
                
                row.update({
                    'training_success': training_results.get('success', False),
                    'training_time_hours': training_results.get('training_time_seconds', 0) / 3600,
                    'best_epoch': model_info.get('best_epoch', 0),
                    'best_fitness': model_info.get('best_fitness', 0),
                    'model_size_mb': model_info.get('model_size_mb', 0)
                })
                
                # Add training config
                if 'training_config' in experiment:
                    config = experiment['training_config'].get('training_parameters', {})
                    row.update({
                        'epochs': config.get('epochs', 0),
                        'batch_size': config.get('batch_size', 0),
                        'learning_rate': config.get('learning_rate', 0),
                        'device': config.get('device', 'unknown')
                    })
            
            rows.append(row)
        
        # Create DataFrame and save
        df = pd.DataFrame(rows)
        
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.results_dir / f'experiments_summary_{timestamp}.csv'
        else:
            output_file = Path(output_file)
        
        output_file.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_file, index=False)
        
        logger.info(f"Results exported to CSV: {output_file}")
        return str(output_file)


def create_results_manager(config: CaminaConfig, results_dir: Union[str, Path] = "results") -> ResultsManager:
    """Create results manager with configuration"""
    return ResultsManager(config, results_dir)