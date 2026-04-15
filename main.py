from ddor import *
from gna import *
from cost_calculations import acc_calculations

if __name__ == '__main__':

    acc_folder = 'C:/Users/user1/Documents/LBNL/projects/CPUC Project/LODGE Work/data'

    # 2023
    data_folder_2023 = os.path.join(
        acc_folder,
        'Confidential- E3 Calculations - 2024 ACC Distribution Data20250403112056'
    )

    """
    ########################
    # PGE
    ########################
    # read pge ddor
    pge_ddor_file_2023 = os.path.join(data_folder_2023, 'PG&E_working draft_to_share.xlsx')
    pge_ddor_dict_2023   = 'parser_data/ddor/ddor_2023_pge_parser.csv'
    pge_d = DDOR(utility_name="PG&E",
                 year=2023,
                 file_path=pge_ddor_file_2023,
                 parsing_dictionary=pge_ddor_dict_2023)

    # read pge gna
    pge_gna_file_2023 = os.path.join(data_folder_2023, 'PG&E_working draft_to_share.xlsx')
    pge_gna_dict_2023 = 'parser_data/gna/gna_2023_pge_parser.csv'
    pge_kl_dict_2023 = 'parser_data/known_loads/kl_2023_pge_parser.csv'
    pge_g = GNA(utility_name="PG&E",
                   year_start=2023, year_end=2027)
    pge_g.add_records(xls_file=pge_gna_file_2023,
                         parsing_csv_file=pge_gna_dict_2023)
    pge_g.add_records(xls_file=pge_gna_file_2023,
                         parsing_csv_file=pge_kl_dict_2023)

    acc_calculations(pge_d, pge_g, utility_marginal_cost_factor=0.0832)

    """

    ########################
    # SCE
    ########################
    # read SCE ddor
    sce_ddor_file_2023 = os.path.join(data_folder_2023,'SCE_working draft_to_share.xlsx')
    SCE_ddor_dict_2023 = 'parser_data/ddor/ddor_2023_sce_parser.csv'
    sce_d_2023 = DDOR(utility_name="SCE",
                    year=2023,
                    file_path=sce_ddor_file_2023,
                    parsing_dictionary=SCE_ddor_dict_2023)

    # read SCE GNA - read separate feeders and substations
    sce_gna_file_2023 = os.path.join(data_folder_2023, 'SCE_working draft_to_share.xlsx')
    sce_gna_feeders_dict_2023 = 'parser_data/gna/gna_2023_SCE_parser.csv'
    sce_kl_feeders_dict_2023 = 'parser_data/known_loads/kl_2023_sce_parser.csv'
    sce_gna_sbs_dict_2023 = 'parser_data/gna/gna_2023_SCE_parser_subs.csv'
    sce_kl_sbs_dict_2023 = 'parser_data/known_loads/kl_2023_sce_parser_subs.csv'

    # read feeders
    sce_fd = GNA(utility_name="SCE_feeders",
                  year_start=2023, year_end=2027)
    sce_fd.add_records(xls_file=sce_gna_file_2023,
                         parsing_csv_file=sce_gna_feeders_dict_2023)
    sce_fd.add_records(xls_file=sce_gna_file_2023,
                         parsing_csv_file=sce_kl_feeders_dict_2023)
    # read subs
    sce_subs = GNA(utility_name="SCE_subs",
                  year_start=2023, year_end=2027)
    sce_subs.add_records(xls_file=sce_gna_file_2023,
                         parsing_csv_file=sce_gna_sbs_dict_2023)
    sce_subs.add_records(xls_file=sce_gna_file_2023,
                         parsing_csv_file=sce_kl_sbs_dict_2023)

    # Create a new GNA based on the
    sce_gna = GNA(utility_name="SCE",
                   year_start=2023, year_end=2027)
    fd = sce_fd.gna_data.copy()
    fd['facility_type'] = 'feeders'

    sbs = sce_subs.gna_data.copy()
    sbs['facility_type'] = 'substations'
    sce_gna.gna_data = pd.concat([fd, sbs])

    acc_calculations(ddor=sce_d_2023,
                     gna=sce_gna,
                     utility_marginal_cost_factor=0.1148,
                     feeder_transfers_ratio=0.2)

