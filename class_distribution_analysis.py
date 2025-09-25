#!/usr/bin/env python3
"""
Class Distribution Analysis for CAMINA Dataset
Calculates total instances and percentages for all urban mobility classes
"""

def analyze_class_distribution():
    # Class data: [Class Name, New Definition, Instances]
    class_data = [
        ("Person", "No (COCO)", 6975),
        ("Cyclist", "Yes (rule-based)", 2012),
        ("Car", "No (COCO)", 2105),
        ("E-scooter", "Yes (open-vocabulary)", 728),
        ("SUV", "Yes (open-vocabulary)", 456),
        ("Motorcyclist", "COCO", 307),
        ("Bus", "COCO", 321),
        ("Delivery Van", "Yes (open-vocabulary)", 112),
        ("Truck", "COCO", 132)
    ]

    # Calculate total instances
    total_instances = sum(instances for _, _, instances in class_data)

    print("=" * 80)
    print("CAMINA Dataset - Class Distribution Analysis")
    print("=" * 80)
    print()

    # Table header
    print(f"{'Class':<15} {'New Definition':<25} {'Instances':<10} {'Percentage':<10}")
    print("-" * 70)

    # Calculate and display percentages
    for class_name, new_def, instances in class_data:
        percentage = (instances / total_instances) * 100
        print(f"{class_name:<15} {new_def:<25} {instances:<10} {percentage:>7.2f}%")

    print("-" * 70)
    print(f"{'TOTAL':<15} {'':<25} {total_instances:<10} {100.0:>7.2f}%")
    print()

    # Additional statistics
    print("Summary Statistics:")
    print(f"• Total Instances: {total_instances:,}")
    print(f"• Number of Classes: {len(class_data)}")
    print(f"• Most Frequent: {max(class_data, key=lambda x: x[2])[0]} ({max(class_data, key=lambda x: x[2])[2]:,} instances)")
    print(f"• Least Frequent: {min(class_data, key=lambda x: x[2])[0]} ({min(class_data, key=lambda x: x[2])[2]:,} instances)")

    # Class imbalance analysis
    max_instances = max(instances for _, _, instances in class_data)
    min_instances = min(instances for _, _, instances in class_data)
    imbalance_ratio = max_instances / min_instances
    print(f"• Class Imbalance Ratio: {imbalance_ratio:.1f}:1")

    print()
    print("Class Categories by Definition Method:")

    # Group by definition method
    coco_classes = [(name, instances) for name, def_method, instances in class_data if "COCO" in def_method]
    rule_based = [(name, instances) for name, def_method, instances in class_data if "rule-based" in def_method]
    open_vocab = [(name, instances) for name, def_method, instances in class_data if "open-vocabulary" in def_method]

    print(f"• COCO Classes ({len(coco_classes)}): {sum(inst for _, inst in coco_classes):,} instances ({sum(inst for _, inst in coco_classes)/total_instances*100:.1f}%)")
    for name, instances in coco_classes:
        print(f"  - {name}: {instances:,}")

    print(f"• Rule-based Classes ({len(rule_based)}): {sum(inst for _, inst in rule_based):,} instances ({sum(inst for _, inst in rule_based)/total_instances*100:.1f}%)")
    for name, instances in rule_based:
        print(f"  - {name}: {instances:,}")

    print(f"• Open-vocabulary Classes ({len(open_vocab)}): {sum(inst for _, inst in open_vocab):,} instances ({sum(inst for _, inst in open_vocab)/total_instances*100:.1f}%)")
    for name, instances in open_vocab:
        print(f"  - {name}: {instances:,}")

if __name__ == "__main__":
    analyze_class_distribution()