import pyvo as vo
tap_service = vo.dal.TAPService("http://dc.g-vo.org/tap")
ex_query = """
    SELECT TOP 5
    source_id, ra, dec, phot_g_mean_mag
    FROM gaia.dr3lite
    WHERE phot_g_mean_mag BETWEEN 19 AND 20
    ORDER BY phot_g_mean_mag
    """
result = tap_service.search(ex_query)
print(result)
