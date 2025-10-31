#!/usr/bin/env python3
"""
Financial Projections Calculator
Compare SaaS model vs Traditional IT consulting model
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List

class FinancialProjections:
    def __init__(self):
        # Traditional model assumptions
        self.traditional = {
            'project_fee': 200000,  # MAD per project
            'annual_support': 50000,  # MAD per year
            'implementation_months': 3,
            'clients_per_year': 12,
            'gross_margin': 0.35,
            'client_lifetime_months': 36
        }
        
        # SaaS model assumptions
        self.saas = {
            'monthly_subscription': 8000,  # MAD per month
            'setup_fee': 0,  # No upfront
            'aws_cost_per_client': 2000,  # MAD per month
            'gross_margin': 0.75,
            'client_lifetime_months': 120,  # 10 years
            'churn_rate_annual': 0.05
        }
    
    def calculate_traditional_model(self, years: int = 5) -> Dict:
        """Calculate projections for traditional IT consulting model"""
        results = {
            'years': [],
            'total_revenue': 0,
            'total_profit': 0,
            'cumulative_clients': 0
        }
        
        cumulative_revenue = 0
        cumulative_clients = 0
        
        for year in range(1, years + 1):
            new_clients = self.traditional['clients_per_year']
            
            # Project fees from new clients
            project_revenue = new_clients * self.traditional['project_fee']
            
            # Support revenue from all active clients
            # (assuming clients from previous years still pay support)
            cumulative_clients += new_clients
            support_revenue = cumulative_clients * self.traditional['annual_support']
            
            year_revenue = project_revenue + support_revenue
            year_profit = year_revenue * self.traditional['gross_margin']
            cumulative_revenue += year_revenue
            
            results['years'].append({
                'year': year,
                'new_clients': new_clients,
                'total_clients': cumulative_clients,
                'revenue': year_revenue,
                'profit': year_profit,
                'cumulative_revenue': cumulative_revenue
            })
        
        results['total_revenue'] = cumulative_revenue
        results['total_profit'] = cumulative_revenue * self.traditional['gross_margin']
        results['cumulative_clients'] = cumulative_clients
        
        return results
    
    def calculate_saas_model(self, years: int = 5) -> Dict:
        """Calculate projections for SaaS cloud model"""
        results = {
            'years': [],
            'total_revenue': 0,
            'total_profit': 0,
            'cumulative_clients': 0,
            'mrr_final': 0
        }
        
        cumulative_revenue = 0
        active_clients = 0
        
        # Growth assumptions
        year_1_clients = 50
        growth_rate = 1.5  # 50% growth per year
        
        for year in range(1, years + 1):
            if year == 1:
                new_clients = year_1_clients
            else:
                new_clients = int(results['years'][-1]['new_clients'] * growth_rate)
            
            # Account for churn
            churned_clients = int(active_clients * self.saas['churn_rate_annual'])
            active_clients = active_clients - churned_clients + new_clients
            
            # Monthly recurring revenue
            mrr = active_clients * self.saas['monthly_subscription']
            year_revenue = mrr * 12
            
            # Costs
            year_costs = active_clients * self.saas['aws_cost_per_client'] * 12
            year_profit = year_revenue - year_costs
            
            cumulative_revenue += year_revenue
            
            results['years'].append({
                'year': year,
                'new_clients': new_clients,
                'churned_clients': churned_clients,
                'active_clients': active_clients,
                'mrr': mrr,
                'revenue': year_revenue,
                'costs': year_costs,
                'profit': year_profit,
                'cumulative_revenue': cumulative_revenue
            })
        
        results['total_revenue'] = cumulative_revenue
        results['total_profit'] = sum(y['profit'] for y in results['years'])
        results['cumulative_clients'] = active_clients
        results['mrr_final'] = results['years'][-1]['mrr']
        
        return results
    
    def calculate_opportunity_cost(self, hours_on_media: int, hours_on_tech: int) -> Dict:
        """Calculate opportunity cost of time spent on non-tech activities"""
        
        # Assumptions
        hourly_value_tech = 500  # MAD per hour (based on consulting rates)
        hourly_value_media = 50  # MAD per hour (much lower value)
        
        results = {
            'weekly_loss': (hours_on_media * hourly_value_tech) - (hours_on_media * hourly_value_media),
            'monthly_loss': 0,
            'annual_loss': 0,
            'potential_clients_lost': 0
        }
        
        results['monthly_loss'] = results['weekly_loss'] * 4
        results['annual_loss'] = results['monthly_loss'] * 12
        
        # Each client needs ~20 hours of initial work
        hours_per_client = 20
        results['potential_clients_lost'] = (hours_on_media * 52) // hours_per_client
        
        return results
    
    def compare_models(self, years: int = 5) -> Dict:
        """Generate comprehensive comparison between models"""
        traditional = self.calculate_traditional_model(years)
        saas = self.calculate_saas_model(years)
        
        comparison = {
            'traditional_model': traditional,
            'saas_model': saas,
            'comparison': {
                'revenue_difference': saas['total_revenue'] - traditional['total_revenue'],
                'profit_difference': saas['total_profit'] - traditional['total_profit'],
                'roi_traditional': (traditional['total_profit'] / traditional['total_revenue']) * 100,
                'roi_saas': (saas['total_profit'] / saas['total_revenue']) * 100,
                'recurring_revenue_advantage': saas['mrr_final'] * 12,  # Annual recurring
                'scalability': 'SaaS model scales without proportional cost increase',
                'cash_flow': 'SaaS provides predictable monthly cash flow'
            }
        }
        
        return comparison
    
    def generate_report(self, years: int = 5) -> str:
        """Generate a formatted report comparing both models"""
        data = self.compare_models(years)
        
        report = f"""
FINANCIAL PROJECTIONS REPORT
Generated: {datetime.now().strftime('%Y-%m-%d')}
Projection Period: {years} Years

========================================
TRADITIONAL IT CONSULTING MODEL
========================================
Total Revenue: {data['traditional_model']['total_revenue']:,.0f} MAD
Total Profit: {data['traditional_model']['total_profit']:,.0f} MAD
Total Clients: {data['traditional_model']['cumulative_clients']}
Gross Margin: {self.traditional['gross_margin']*100:.0f}%

Year-by-Year Breakdown:
"""
        for year_data in data['traditional_model']['years']:
            report += f"""
Year {year_data['year']}:
  New Clients: {year_data['new_clients']}
  Revenue: {year_data['revenue']:,.0f} MAD
  Profit: {year_data['profit']:,.0f} MAD
"""
        
        report += f"""
========================================
SAAS CLOUD MODEL
========================================
Total Revenue: {data['saas_model']['total_revenue']:,.0f} MAD
Total Profit: {data['saas_model']['total_profit']:,.0f} MAD
Active Clients (Year {years}): {data['saas_model']['cumulative_clients']}
Final MRR: {data['saas_model']['mrr_final']:,.0f} MAD
Gross Margin: {self.saas['gross_margin']*100:.0f}%

Year-by-Year Breakdown:
"""
        for year_data in data['saas_model']['years']:
            report += f"""
Year {year_data['year']}:
  New Clients: {year_data['new_clients']}
  Active Clients: {year_data['active_clients']}
  MRR: {year_data['mrr']:,.0f} MAD
  Annual Revenue: {year_data['revenue']:,.0f} MAD
  Profit: {year_data['profit']:,.0f} MAD
"""
        
        report += f"""
========================================
COMPARATIVE ANALYSIS
========================================
Revenue Advantage (SaaS): {data['comparison']['revenue_difference']:,.0f} MAD
Profit Advantage (SaaS): {data['comparison']['profit_difference']:,.0f} MAD
ROI Traditional: {data['comparison']['roi_traditional']:.1f}%
ROI SaaS: {data['comparison']['roi_saas']:.1f}%

KEY INSIGHTS:
1. SaaS model generates {(data['saas_model']['total_revenue'] / data['traditional_model']['total_revenue']):.1f}x more revenue
2. Predictable MRR of {data['saas_model']['mrr_final']:,.0f} MAD by year {years}
3. Higher customer lifetime value (10 years vs 3 years)
4. Scalable without proportional cost increase
5. Better cash flow with monthly payments

RECOMMENDATION:
Focus 100% on SaaS model. Every day spent on non-SaaS activities 
costs approximately {(data['saas_model']['mrr_final'] / 30):,.0f} MAD in potential MRR.
"""
        
        return report


def main():
    calculator = FinancialProjections()
    
    # Generate 5-year projection
    print(calculator.generate_report(5))
    
    # Calculate opportunity cost example
    print("\n" + "="*40)
    print("OPPORTUNITY COST ANALYSIS")
    print("="*40)
    
    # Example: 20 hours/week on media, could be on tech
    opportunity = calculator.calculate_opportunity_cost(
        hours_on_media=20,
        hours_on_tech=20
    )
    
    print(f"""
Time spent on media projects: 20 hours/week
Opportunity Cost:
  Weekly Loss: {opportunity['weekly_loss']:,.0f} MAD
  Monthly Loss: {opportunity['monthly_loss']:,.0f} MAD
  Annual Loss: {opportunity['annual_loss']:,.0f} MAD
  Potential Clients Lost: {opportunity['potential_clients_lost']} per year

CONCLUSION: Every hour on media instead of tech costs real money.
""")
    
    # Save detailed data to JSON
    with open('financial_projections.json', 'w') as f:
        json.dump(calculator.compare_models(5), f, indent=2)
    print("\nDetailed projections saved to: financial_projections.json")


if __name__ == "__main__":
    main()
