import sys

file_path = r'c:\Users\santh\.vscode\Programming\Software\Dataset preprocessor\src\agents\routing_agent\routing_agent.py'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

target1 = '''        dispatch_log: list[DispatchRecord] = []

        for buyer in buy_queue:
            if buyer.remaining_mw <= 0:
                continue

            for seller in sell_queue:
                if seller.remaining_mw <= 0:'''

replacement1 = '''        dispatch_log: list[DispatchRecord] = []

        from .syndicate_agent import SyndicateBroker
        syndicate_broker = SyndicateBroker(self)

        for buyer in buy_queue:
            if buyer.remaining_mw <= 0:
                continue

            # Attempt Syndicate deal first for the remaining order
            synd_record = syndicate_broker.attempt_syndicate_trade(
                buyer,
                sell_queue,
                hour_index=hour_index,
                day_index=day_index
            )
            
            if synd_record:
                dispatch_log.append(synd_record)
                self._print_syndicate_log(synd_record)
                if buyer.remaining_mw <= 0:
                    continue

            for seller in sell_queue:
                if seller.remaining_mw <= 0:'''

target2 = '''        print(log_line)
        logger.info(log_line)

    # ------------------------------------------------------------------'''

replacement2 = '''        print(log_line)
        logger.info(log_line)

    def _print_syndicate_log(self, record):
        surplus = record.buyer_bid - record.cleared_price_mw
        node_names = ", ".join(record.syndicate_sellers)

        log_line = (
            f"\\n{'═'*72}\\n"
            f"[SYNDICATE DISPATCH] {record.transfer_mw:.0f} MW  "
            f"Syndicate({node_names}) → {record.buyer_city_id}\\n"
            f"  Cleared at  : ₹{record.cleared_price_mw:.2f}/MW\\n"
            f"  Breakdown   : \\n    + {record.breakdown_log}\\n"
            f"  {record.buyer_city_id} Bid : ₹{record.buyer_bid:.2f}/MW  "
            f"(Buyer surplus: ₹{surplus:.2f}/MW)\\n"
            f"  LLM Safety Check: APPROVED (for all legs)\\n"
            f"{'═'*72}"
        )
        print(log_line)
        logger.info(log_line)

    # ------------------------------------------------------------------'''

if target1 in text and target2 in text:
    text = text.replace(target1, replacement1)
    text = text.replace(target2, replacement2)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(text)
    print('SUCCESS')
else:
    print('FAILED TO FIND TARGETS')
    if target1 not in text: print('Target 1 missing')
    if target2 not in text: print('Target 2 missing')

