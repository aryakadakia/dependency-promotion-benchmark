# Human coding

coding_part1.xlsx, coding_part2.xlsx  the primary coder's workbooks
coding_key.json                       maps workbook rows back to frame turns
handcoded.json                        the parsed result: 100 turns, 397 judgements, 25 blind repeats

second_coder_packet.xlsx              the blind packet, as sent
second_coder_packet_returned_*.xlsx        the packet as returned, with answers
second_coder_key.json                 its mapping; do not send this with the packet
second_coded.json                     the parsed result: 40 turns, 142 judgements, 2 skips

The packet carries no scenario, model or condition column, so its answers mean nothing
without the key. second_coder_read.py reconstructs each item's exchange text from the
frame and compares it byte-for-byte before writing anything, so a shift in item order
fails loudly instead of pairing every answer with the wrong reply.

Built and read by coding_workbook.py, second_coder_packet.py and second_coder_read.py.
