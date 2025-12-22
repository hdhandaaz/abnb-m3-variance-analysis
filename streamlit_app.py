import streamlit as st
import pandas as pd
from io import BytesIO

def categorize_billing_type(row):
    if row['category'] not in ['Invoice-Rebill', 'Invoice-CM']:
        return None
    cfid = str(row['invoice_cfid'])
    if cfid.isdigit() or cfid.endswith('G') or '_' in cfid:
        return 'Manual'
    elif 'PT' in cfid:
        return 'Principal Trading'
    return 'Automated'

def process_datasets(fastdb_file, im_file):
    fastdb = pd.read_excel(fastdb_file) if fastdb_file.name.endswith('.xlsx') else pd.read_csv(fastdb_file, encoding='latin-1', encoding_errors='ignore')
    im = pd.read_excel(im_file) if im_file.name.endswith('.xlsx') else pd.read_csv(im_file, encoding='latin-1', encoding_errors='ignore')
    
    fastdb.iloc[:, 5] = pd.to_numeric(fastdb.iloc[:, 5], errors='coerce')
    im.iloc[:, 3] = pd.to_numeric(im.iloc[:, 3], errors='coerce')
    
    fastdb.columns = fastdb.columns.str.strip()
    im.columns = im.columns.str.strip()
    
    fastdb['OFA_Billing_Type'] = fastdb.apply(categorize_billing_type, axis=1)
    fastdb['campaign_ID_Transformed'] = "'" + fastdb.iloc[:, 7].astype(str)
    
    fastdb_amount, fastdb_campaign, fastdb_category, fastdb_invoice = fastdb.columns[5], fastdb.columns[7], fastdb.columns[9], fastdb.columns[16]
    im_amount, im_campaign, im_invoice, im_subledger = im.columns[3], im.columns[2], im.columns[13], im.columns[15]
    
    im[im_subledger] = im[im_subledger].astype(str).str.strip()
    fastdb[fastdb_category] = fastdb[fastdb_category].astype(str).str.strip()
    
    results = {}
    results['Automated Revenue'] = (im[im[im_subledger].isin(['IMDArevenue', 'IMDSTrevenue', 'IM_DA_Revenue', 'IM_DST_Revenue'])][im_amount].sum(), fastdb[fastdb[fastdb_category] == 'Revenue'][fastdb_amount].sum())
    results['Automated Invoices + Credit Memos'] = (im[im[im_subledger].isin(['IMDAPWO', 'IM_DA_PWO'])][im_amount].sum(), fastdb[(fastdb[fastdb_category].isin(['Invoice-Rebill', 'Invoice-CM'])) & (fastdb['OFA_Billing_Type'] == 'Automated')][fastdb_amount].sum())
    results['Principal Trading Invoices'] = (im[im[im_subledger] == 'PT_invoice'][im_amount].sum(), fastdb[(fastdb[fastdb_category].isin(['Invoice-Rebill', 'Invoice-CM'])) & (fastdb['OFA_Billing_Type'] == 'Principal Trading')][fastdb_amount].sum())
    results['OFA M2 Manual Billing'] = (im[im[im_subledger].isin(['OFAManualPWO', 'OFAManualADJ_PWO', 'OFA_Manual_PWO', 'OFA_Manual_Adj_PWO'])][im_amount].sum(), fastdb[(fastdb[fastdb_category].isin(['Invoice-Rebill', 'Invoice-CM'])) & (fastdb['OFA_Billing_Type'] == 'Manual')][fastdb_amount].sum())
    results['OFA M2 Manual Revenue'] = (im[im[im_subledger].isin(['OFAManualrevenue', 'OFAManualAdj_revenue', 'OFA_Manual_Revenue', 'OFA_Manual_Adj_Revenue'])][im_amount].sum(), 0)
    results['ABNB-Adjustments'] = (0, fastdb[fastdb[fastdb_category] == 'ABNB-Adjustment'][fastdb_amount].sum())
    results['Other-Adjustments'] = (0, fastdb[~fastdb[fastdb_category].isin(['Revenue', 'Invoice-Rebill', 'Invoice-CM', 'ABNB-Adjustment'])][fastdb_amount].sum())
    
    logic_map = {
        'Automated Revenue': ('im_subledger_input = IM_DA_Revenue, IM_DST_Revenue', 'category = Revenue'),
        'Automated Invoices + Credit Memos': ('im_subledger_input = IM_DA_PWO', 'category = Invoice-Rebill/Invoice-CM AND OFA_Billing_Type = Automated'),
        'Principal Trading Invoices': ('im_subledger_input = PT_invoice', 'category = Invoice-Rebill/Invoice-CM AND OFA_Billing_Type = Principal Trading'),
        'OFA M2 Manual Billing': ('im_subledger_input = OFA_Manual_PWO, OFA_Manual_Adj_PWO', 'category = Invoice-Rebill/Invoice-CM AND OFA_Billing_Type = Manual'),
        'OFA M2 Manual Revenue': ('im_subledger_input = OFA_Manual_Revenue, OFA_Manual_Adj_Revenue', 'N/A - Does not exist in FastDB'),
        'ABNB-Adjustments': ('N/A - Does not exist in IM M3', 'category = ABNB-Adjustment'),
        'Other-Adjustments': ('N/A - Does not exist in IM M3', 'All uncategorized records')
    }
    summary = pd.DataFrame([{'Activity Category': cat, 'Iron Mountain M3 Subledger Amount': float(vals[0]), 'FastDB Amount': float(vals[1]), 'Variance': float(vals[0] - vals[1]), 'Absolute Variance': abs(float(vals[0] - vals[1])), 'IM M3 Logic': logic_map[cat][0], 'FastDB Logic': logic_map[cat][1]} for cat, vals in results.items()])
    totals = pd.DataFrame([{'Activity Category': 'TOTAL', 'Iron Mountain M3 Subledger Amount': float(summary['Iron Mountain M3 Subledger Amount'].sum()), 'FastDB Amount': float(summary['FastDB Amount'].sum()), 'Variance': float(summary['Variance'].sum()), 'Absolute Variance': None, 'IM M3 Logic': '', 'FastDB Logic': ''}])
    summary = pd.concat([summary, totals], ignore_index=True)
    
    variance_tabs = {}
    if abs(results['Automated Revenue'][1] - results['Automated Revenue'][0]) > 100:
        im_rev = im[im[im_subledger].isin(['IMDArevenue', 'IMDSTrevenue', 'IM_DA_Revenue', 'IM_DST_Revenue'])].groupby(im_campaign)[im_amount].sum()
        fastdb_rev = fastdb[fastdb[fastdb_category] == 'Revenue'].groupby('campaign_ID_Transformed')[fastdb_amount].sum()
        campaigns = pd.Index(im_rev.index).union(pd.Index(fastdb_rev.index))
        var_df = pd.DataFrame({'Campaign ID': campaigns, 'Iron Mountain M3 Subledger Amount': [float(im_rev.get(c, 0)) for c in campaigns], 'FastDB Amount': [float(fastdb_rev.get(c, 0)) for c in campaigns]})
        var_df['Variance'] = var_df['Iron Mountain M3 Subledger Amount'] - var_df['FastDB Amount']
        var_df['Absolute Variance'] = var_df['Variance'].abs()
        variance_tabs['Automated Revenue Variance'] = var_df.sort_values('Absolute Variance', ascending=False)
    
    if abs(results['Automated Invoices + Credit Memos'][1] - results['Automated Invoices + Credit Memos'][0]) > 100:
        im_inv = im[im[im_subledger].isin(['IMDAPWO', 'IM_DA_PWO'])].groupby(im_invoice)[im_amount].sum()
        fastdb_inv = fastdb[(fastdb[fastdb_category].isin(['Invoice-Rebill', 'Invoice-CM'])) & (fastdb['OFA_Billing_Type'] == 'Automated')].groupby(fastdb_invoice)[fastdb_amount].sum()
        invoices = pd.Index(im_inv.index).union(pd.Index(fastdb_inv.index))
        var_df = pd.DataFrame({'Invoice CFID': invoices, 'Iron Mountain M3 Subledger Amount': [float(im_inv.get(i, 0)) for i in invoices], 'FastDB Amount': [float(fastdb_inv.get(i, 0)) for i in invoices]})
        var_df['Variance'] = var_df['Iron Mountain M3 Subledger Amount'] - var_df['FastDB Amount']
        var_df['Absolute Variance'] = var_df['Variance'].abs()
        variance_tabs['Automated Invoices + CM Variance'] = var_df.sort_values('Absolute Variance', ascending=False)
    
    if abs(results['Principal Trading Invoices'][1] - results['Principal Trading Invoices'][0]) > 100:
        im_pt = im[im[im_subledger] == 'PT_invoice'].groupby(im_invoice)[im_amount].sum()
        fastdb_pt = fastdb[(fastdb[fastdb_category].isin(['Invoice-Rebill', 'Invoice-CM'])) & (fastdb['OFA_Billing_Type'] == 'Principal Trading')].groupby(fastdb_invoice)[fastdb_amount].sum()
        invoices = pd.Index(im_pt.index).union(pd.Index(fastdb_pt.index))
        var_df = pd.DataFrame({'Invoice CFID': invoices, 'Iron Mountain M3 Subledger Amount': [float(im_pt.get(i, 0)) for i in invoices], 'FastDB Amount': [float(fastdb_pt.get(i, 0)) for i in invoices]})
        var_df['Variance'] = var_df['Iron Mountain M3 Subledger Amount'] - var_df['FastDB Amount']
        var_df['Absolute Variance'] = var_df['Variance'].abs()
        variance_tabs['Principal Trading Variance'] = var_df.sort_values('Absolute Variance', ascending=False)
    
    if abs(results['OFA M2 Manual Billing'][1] - results['OFA M2 Manual Billing'][0]) > 100:
        im_manual = im[im[im_subledger].isin(['OFAManualPWO', 'OFAManualADJ_PWO', 'OFA_Manual_PWO', 'OFA_Manual_Adj_PWO'])].groupby(im_invoice)[im_amount].sum()
        fastdb_manual = fastdb[(fastdb[fastdb_category].isin(['Invoice-Rebill', 'Invoice-CM'])) & (fastdb['OFA_Billing_Type'] == 'Manual')].groupby(fastdb_invoice)[fastdb_amount].sum()
        invoices = pd.Index(im_manual.index).union(pd.Index(fastdb_manual.index))
        manual_pwo_invoices = set(im[im[im_subledger].isin(['OFAManualPWO', 'OFA_Manual_PWO'])][im_invoice].unique())
        manual_adj_invoices = set(im[im[im_subledger].isin(['OFAManualADJ_PWO', 'OFA_Manual_Adj_PWO'])][im_invoice].unique())
        var_df = pd.DataFrame({'Invoice CFID': invoices, 'Iron Mountain M3 Subledger Amount': [float(im_manual.get(i, 0)) for i in invoices], 'FastDB Amount': [float(fastdb_manual.get(i, 0)) for i in invoices]})
        var_df['Variance'] = var_df['Iron Mountain M3 Subledger Amount'] - var_df['FastDB Amount']
        var_df['Absolute Variance'] = var_df['Variance'].abs()
        var_df['Manual OFA Invoice_CM'] = ['Y' if i in manual_pwo_invoices else 'N' for i in invoices]
        var_df['Manual OFA Adjustment'] = ['Y' if i in manual_adj_invoices else 'N' for i in invoices]
        variance_tabs['OFA M2 Manual Billing Variance'] = var_df.sort_values('Absolute Variance', ascending=False)
    
    return summary, variance_tabs, fastdb, im

st.set_page_config(page_title="ABNB M3 Variance Analysis", layout="wide")
st.title("ABNB M3 - ADSP Transactional Activity UAT")

col1, col2 = st.columns(2)
with col1:
    market = st.text_input("🌍 Market/Country", placeholder="e.g., US, UK, APAC")
    fastdb_file = st.file_uploader("📁 FastDB Dataset", type=['xlsx', 'xls', 'csv'])
with col2:
    activity_period = st.text_input("📅 Activity Period", placeholder="e.g., 2024-Q1, Jan2024")
    im_file = st.file_uploader("📁 Iron Mountain M3 Subledger", type=['xlsx', 'xls', 'csv'])

if fastdb_file and im_file:
    if st.button("🔄 Generate Variance Analysis", type="primary"):
        with st.spinner("Processing..."):
            summary, variance_tabs, fastdb, im = process_datasets(fastdb_file, im_file)
            
            st.success("✅ Analysis Complete!")
            st.subheader("Summary Analysis")
            st.dataframe(summary, use_container_width=True)
            
            for tab_name, df in variance_tabs.items():
                st.subheader(tab_name)
                st.dataframe(df, use_container_width=True)
            
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                summary.to_excel(writer, sheet_name='Summary Analysis', index=False)
                for tab_name, df in variance_tabs.items():
                    df.to_excel(writer, sheet_name=tab_name[:31], index=False)
                fastdb.to_excel(writer, sheet_name='FastDB Transformed', index=False)
                im.to_excel(writer, sheet_name='Iron Mountain M3', index=False)
            
            filename = f"ABNB M3 Transactional UAT - {market} {activity_period}.xlsx" if market and activity_period else "variance_analysis.xlsx"
            st.download_button("⬇️ Download Excel Report", output.getvalue(), filename, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
