# ── Seat & Pricing Config ─────────────────────────────────
CLASS_CONFIG = {
    "AC Business": {"coaches":["A1","A2"],          "cabins_per_coach":4,"berths_per_cabin":6,
                    "berth_labels":["1-Lower","2-Middle","3-Upper","4-Lower","5-Middle","6-Upper"]},
    "AC Standard": {"coaches":["B1","B2","B3"],     "cabins_per_coach":6,"berths_per_cabin":6,
                    "berth_labels":["1-Lower","2-Middle","3-Upper","4-Lower","5-Middle","6-Upper"]},
    "Economy":     {"coaches":["C1","C2","C3","C4"],"cabins_per_coach":8,"berths_per_cabin":6,
                    "berth_labels":["1-Lower","2-Middle","3-Upper","4-Lower","5-Middle","6-Upper"]},
}

BASE_CLASS_PRICES = {"AC Business":13250,"AC Standard":6500,"Economy":3500}
RABTA_CHARGE      = 10
REFUND_PERCENT    = 0.85
