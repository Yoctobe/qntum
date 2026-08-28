"""
MAIN ENTRY POINT — QUANTUM MODEL V2
═══════════════════════════════════════════════════════════════════════════════

Two-phase validation and application:

PHASE 1: PHYSICS VALIDATION
    Test on known ground truth physics phenomena
    SUCCESS CRITERIA: Mean correlation > 0.90, MAE < 0.15
    
PHASE 2: FINANCIAL APPLICATION
    Apply validated model to financial/economic data
    Forecast future states with confidence intervals

Usage:
    python main_v2.py                           # Run both phases with demo data
    python main_v2.py --physics-only            # Only physics validation
    python main_v2.py --financial data.csv      # Physics validation then financial forecast
"""

import sys
import argparse
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

from quantum_model.data_preprocessor import DataPreprocessor, load_and_normalize
from quantum_model.influence_matrix_v2 import InfluenceMatrixV2
from quantum_model.quantum_v2 import QuantumV2, build_quantum_v2, Event
from quantum_model.physics_tests import PhysicsTestSuite


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 1: PHYSICS VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

def run_physics_validation() -> bool:
    """
    Run complete physics validation suite.
    
    Returns True if all tests pass.
    """
    print("\n" + "="*80)
    print("PHASE 1: PHYSICS VALIDATION")
    print("="*80)
    print("Testing model on phenomena with known ground truth...")
    print()
    
    suite = PhysicsTestSuite(output_dir="physics_test_results")
    suite.run_all_tests()
    
    # Check if all passed
    passed = all(r['passed'] for r in suite.results)
    
    if passed:
        print("✓ PHASE 1 COMPLETE: All physics tests passed")
        print("  → Model validated on ground truth")
        print("  → Proceeding to financial data...")
    else:
        print("△ PHASE 1 WARNING: Some physics tests failed")
        print("  → Review model configuration before production use")
    
    return passed


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 2: FINANCIAL APPLICATION
# ══════════════════════════════════════════════════════════════════════════════

def run_financial_forecast(
    csv_path: str,
    forecast_steps: int = 8,
    plot: bool = True,
) -> dict:
    """
    Apply validated model to financial data and generate forecast.
    
    Parameters
    ----------
    csv_path       : path to CSV with level values
    forecast_steps : number of steps ahead to forecast
    plot           : generate visualization
    
    Returns
    -------
    dict with forecast results
    """
    print("\n" + "="*80)
    print("PHASE 2: FINANCIAL FORECAST")
    print("="*80)
    print(f"Loading data from: {csv_path}")
    
    # Load and normalize.
    # Default transform is first difference (safe for rates, zero-crossing and
    # negative series); positive multiplicative series opt into log-differences.
    normalized, params, variable_names = load_and_normalize(
        csv_path,
        date_column="Date",
        skip_columns=["Source"],
        transform_overrides={"SP500": "log_diff", "DXY": "log_diff"},
    )
    
    # Load dates from CSV and detect frequency
    import pandas as pd
    from dateutil.relativedelta import relativedelta
    
    df_with_dates = pd.read_csv(csv_path)
    if 'Date' in df_with_dates.columns:
        dates = pd.to_datetime(df_with_dates['Date'])
        # Detect frequency and calculate dt (time step in days)
        if len(dates) > 1:
            delta_days = (dates.iloc[1] - dates.iloc[0]).days
            if delta_days > 60:
                freq = 'Q'  # Quarterly
                dt = 90.0  # ~90 days per quarter
                delta_func = lambda d, n: d + relativedelta(months=3*n)
            elif delta_days > 20:
                freq = 'M'  # Monthly
                dt = 30.0  # ~30 days per month
                delta_func = lambda d, n: d + relativedelta(months=n)
            else:
                freq = 'W'  # Weekly
                dt = 7.0   # 7 days per week
                delta_func = lambda d, n: d + relativedelta(weeks=n)
        else:
            freq = None
            dt = 1.0  # default to daily
            delta_func = None
    else:
        dates = None
        freq = None
        dt = 1.0
        delta_func = None
    
    print(f"\nData loaded: {len(normalized)} time steps × {len(variable_names)} variables")
    print(f"Variables: {variable_names}")
    print(f"Frequency detected: {freq if freq else 'Unknown'}")
    print(f"Time step (dt): {dt:.1f} days")
    
    prep = DataPreprocessor()
    print("\n" + prep.summary(params))
    
    # Parameter-agnostic: same dynamics as physics validation (auto-discover from data)
    print("\nUsing physics-validated model parameters (α=0.85, β=0.50, auto-discovery)")
    
    # Split train/test
    split = int(len(normalized) * 0.7)
    train_data = normalized[:split]
    test_data = normalized[split:]
    
    print(f"\nTrain/test split: {split}/{len(normalized) - split} steps")
    
    print("\nBuilding Quantum model...")
    # min_corr=0.5: with ~16 training observations, |r| below ~0.5 is not
    # statistically significant — lower thresholds fit noise, not structure
    model = build_quantum_v2(
        train_data,
        variable_names,
        dt=dt,
        search_lags=True,
        lag_search_steps=10,
        min_corr=0.50,
        discover_pairs=True,
        discover_triplets=False,
        discover_quadruplets=False,
        alpha=0.85,
        beta=0.50,
    )
    
    print("\n" + model.I.summary(variable_names))
    
    # Validate on test data
    print("\nValidating on test data...")
    validation = model.validate(normalized, variable_names, train_fraction=0.7)
    
    print(f"\nVALIDATION RESULTS:")
    print(f"{'─'*80}")
    print(f"MAE:  {validation['mae']:.4f}")
    print(f"RMSE: {validation['rmse']:.4f}")
    print(f"\nPer-variable correlations:")
    for var, corr in validation['correlations'].items():
        status = "✓" if corr > 0.5 else "△" if corr > 0.3 else "✗"
        print(f"  {status} {var:<24} r = {corr:+.4f}")
    
    mean_corr = np.mean(list(validation['correlations'].values()))
    print(f"\nMean correlation: {mean_corr:.4f}")
    
    # Pure multi-step forecasting using FIXED dynamics
    print(f"\n{'─'*80}")
    print(f"Generating {forecast_steps}-step ahead forecast...")
    print("(Using fixed quantum dynamics learned from training data)")
    
    # Create events for forecast
    last_state = normalized[-1]
    events = [
        Event(
            t0=0,
            tf=0.0,
            tau=float(forecast_steps + 10),
            initial_magnitude=float(last_state[i]),
            base_level=0.0,
            name=variable_names[i],
        )
        for i in range(len(variable_names))
    ]
    
    # Multi-step forecast using model with history context
    # For quarterly data, provide sufficient history for lag calculations
    history_window = min(20, len(normalized))
    initial_history = normalized[-history_window:]
    
    # Noise scale = one-step-ahead RMSE, so CIs reflect actual model error
    forecast = model.forecast(
        events,
        n_steps=forecast_steps,
        initial_state=last_state,
        initial_history=initial_history,  # CRITICAL: Provide history for lags
        n_bootstrap=300,
        noise_scale=validation['rmse'],
    )
    
    print("\nFORECAST (normalized space):")
    print(f"{'─'*80}")
    print(f"{'Variable':<24} " + "  ".join([f"T+{i+1:>2}" for i in range(min(5, forecast_steps))]))
    print(f"{'─'*80}")
    for i, var in enumerate(variable_names):
        row = f"{var:<24}"
        for k in range(min(5, forecast_steps)):
            row += f" {forecast['point'][k, i]:>+5.2f}"
        print(row)
    
    # Convert back to level space for interpretation
    print(f"\n{'─'*80}")
    print("Converting forecast back to level values...")
    
    prep_for_inverse = DataPreprocessor()
    
    # Get the last known level values from the original data
    import pandas as pd
    df_original = pd.read_csv(csv_path)
    df_original = df_original.drop(columns=[c for c in ['Date', 'Source'] if c in df_original.columns])
    df_original = df_original.select_dtypes(include=[np.number])
    last_level_values = df_original.iloc[-1].values
    
    # Convert forecast to levels
    forecast_levels = prep_for_inverse.inverse_transform(
        forecast['point'],
        params,
        initial_levels=last_level_values,
    )
    
    # Skip first row (initial state) to get actual forecast steps
    forecast_levels = forecast_levels[1:]
    
    # Confidence intervals: inverse-transform each bootstrap path to levels,
    # THEN take percentiles. Inverse-transforming the percentile paths would
    # compound the worst-case increment every step and vastly overstate the CI.
    if 'samples' in forecast:
        level_samples = np.stack([
            prep_for_inverse.inverse_transform(
                sample, params, initial_levels=last_level_values
            )[1:]
            for sample in forecast['samples']
        ])
        forecast_lower = np.percentile(level_samples, 5, axis=0)
        forecast_upper = np.percentile(level_samples, 95, axis=0)
    else:
        forecast_lower = None
        forecast_upper = None
    
    print("\nFORECAST (level values):")
    print(f"{'─'*80}")
    print(f"{'Variable':<24} {'Current':<12} " + "  ".join([f"T+{i+1:>2}" for i in range(min(3, forecast_steps))]))
    print(f"{'─'*80}")
    for i, var in enumerate(variable_names):
        current_val = last_level_values[i]
        row = f"{var:<24} {current_val:>11.2f}"
        for k in range(min(3, forecast_steps)):
            row += f" {forecast_levels[k, i]:>8.2f}"
        print(row)
    
    # Get test data in level values for plotting
    # test_data comes from normalized[split:] which is 7 rows
    # We need corresponding dates and level values
    test_data_level = df_original.iloc[split+1:].values  # +1 because normalized loses first row
    
    # Get dates for plotting
    if dates is not None:
        # Historical dates: align with test_data_level length
        historical_dates = dates.iloc[split+1:].tolist()
        
        # Generate forecast dates
        last_date = dates.iloc[-1]
        forecast_dates = [delta_func(last_date, i+1) for i in range(forecast_steps)]
    else:
        historical_dates = None
        forecast_dates = None
    
    # Plot
    if plot:
        plot_forecast(
            forecast,
            variable_names,
            test_data,  # normalized (kept for signature)
            test_data_level,  # LEVEL values
            forecast_levels,  # LEVEL values
            forecast_lower,  # LEVEL values
            forecast_upper,  # LEVEL values
            historical_dates,  # DATES
            forecast_dates,  # DATES
            save_path="financial_forecast.png",
        )
    
    print(f"\n{'='*80}")
    print("PHASE 2 COMPLETE")
    print(f"{'='*80}\n")
    
    return {
        'forecast': forecast,
        'forecast_levels': forecast_levels,
        'forecast_lower': forecast_lower,
        'forecast_upper': forecast_upper,
        'forecast_dates': forecast_dates,
        'validation': validation,
        'model': model,
        'params': params,
        'variable_names': variable_names,
    }


def plot_forecast(
    forecast: dict,
    variable_names: list[str],
    test_data_normalized: np.ndarray,
    test_data_level: np.ndarray,
    forecast_levels: np.ndarray,
    forecast_lower_levels: np.ndarray = None,
    forecast_upper_levels: np.ndarray = None,
    historical_dates: list = None,
    forecast_dates: list = None,
    save_path: str = "forecast.png",
):
    """
    Generate forecast visualization in LEVEL VALUES with DATES on x-axis.
    """
    n_vars = len(variable_names)
    n_steps = len(forecast_levels)
    
    fig, axes = plt.subplots(
        (n_vars + 1) // 2, 2,
        figsize=(14, 3 * ((n_vars + 1) // 2)),
    )
    axes = np.atleast_2d(axes).flatten()
    
    has_ci = forecast_lower_levels is not None
    
    for i, (var, ax) in enumerate(zip(variable_names, axes)):
        # Historical test data (LEVEL VALUES) with DATES
        if historical_dates is not None:
            ax.plot(historical_dates, test_data_level[:, i], 'o-', label='Historical', 
                   color='C0', alpha=0.7, linewidth=2, markersize=5)
        else:
            hist_x = np.arange(-len(test_data_level), 0)
            ax.plot(hist_x, test_data_level[:, i], 'o-', label='Historical', 
                   color='C0', alpha=0.7, linewidth=2, markersize=5)
        
        # Forecast (LEVEL VALUES) with DATES
        if forecast_dates is not None:
            ax.plot(forecast_dates, forecast_levels[:, i], 's-', label='Forecast', 
                   color='C1', linewidth=2, markersize=5)
            
            # Confidence intervals
            if has_ci:
                ax.fill_between(
                    forecast_dates,
                    forecast_lower_levels[:, i],
                    forecast_upper_levels[:, i],
                    alpha=0.2,
                    color='C1',
                    label='90% CI',
                )
            
            # Vertical line at last historical date
            if historical_dates is not None:
                ax.axvline(historical_dates[-1], color='gray', 
                          linestyle='--', alpha=0.5, linewidth=1.5)
        else:
            fc_x = np.arange(0, n_steps)
            ax.plot(fc_x, forecast_levels[:, i], 's-', label='Forecast', 
                   color='C1', linewidth=2, markersize=5)
            
            if has_ci:
                ax.fill_between(
                    fc_x,
                    forecast_lower_levels[:, i],
                    forecast_upper_levels[:, i],
                    alpha=0.2,
                    color='C1',
                    label='90% CI',
                )
            ax.axvline(0, color='gray', linestyle='--', alpha=0.5, linewidth=1.5)
        
        ax.set_title(var, fontsize=11, fontweight='bold')
        ax.set_ylabel('Level value', fontsize=10)
        ax.set_xlabel('Date' if historical_dates is not None else 'Time step', fontsize=10)
        
        # Rotate date labels
        if historical_dates is not None:
            ax.tick_params(axis='x', rotation=45)
        
        ax.legend(fontsize=8, loc='best')
        ax.grid(alpha=0.3)
    
    # Hide extra subplots
    for j in range(n_vars, len(axes)):
        axes[j].set_visible(False)
    
    plt.suptitle('Quantum Model Forecast (Level Values)', fontsize=13, fontweight='bold')
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\nForecast plot saved → {save_path}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Quantum Model V2 — Physics Validation + Financial Forecast")
    parser.add_argument(
        '--physics-only',
        action='store_true',
        help='Run only physics validation tests',
    )
    parser.add_argument(
        '--financial',
        type=str,
        default=None,
        help='Path to financial data CSV (runs after physics validation)',
    )
    parser.add_argument(
        '--forecast-steps',
        type=int,
        default=8,
        help='Number of steps ahead to forecast (default: 8)',
    )
    
    args = parser.parse_args()
    
    # PHASE 1: Physics validation (always runs — model is parameter-agnostic)
    physics_passed = run_physics_validation()
    
    if not physics_passed:
        print("\n⚠ WARNING: Physics validation had failures")
        print("  Continuing to financial data, but results may be unreliable")
    
    if args.physics_only:
        print("\n✓ Physics validation complete (--physics-only mode)")
        return
    
    # PHASE 2: Financial forecast
    if args.financial:
        csv_path = args.financial
    else:
        # Use default data if available
        default_path = Path("data_us_fed_macro.csv")
        if default_path.exists():
            csv_path = str(default_path)
        else:
            # Check in Model directory
            default_path = Path("Model/data_us_fed_macro.csv")
            if default_path.exists():
                csv_path = str(default_path)
            else:
                print("\n✗ No financial data provided and no default data found")
                print("  Usage: python main_v2.py --financial data.csv")
                return
    
    results = run_financial_forecast(
        csv_path,
        forecast_steps=args.forecast_steps,
        plot=True,
    )
    
    # Save combined historical + forecast CSV (gitignored)
    if results and results.get('forecast_dates') is not None:
        import pandas as pd

        formatted_dates = [d.strftime('%Y-%m-%d') for d in results['forecast_dates']]
        df_original = pd.read_csv(csv_path)

        forecast_rows = pd.DataFrame({
            'Date': formatted_dates,
            'Source': ['forecast'] * len(results['forecast_dates']),
        })
        for i, var in enumerate(results['variable_names']):
            forecast_rows[var] = results['forecast_levels'][:, i].round(2)

        combined_csv = csv_path.replace('.csv', '_with_forecast.csv')
        pd.concat([df_original, forecast_rows], ignore_index=True).to_csv(
            combined_csv, index=False
        )
        print(f"✓ Forecast saved: {combined_csv}")
    
    print("\n" + "="*80)
    print("QUANTUM MODEL V2 — COMPLETE")
    print("="*80)
    print("✓ Physics validation complete")
    print("✓ Financial forecast generated")
    print("  → Review plots and forecast tables above")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
