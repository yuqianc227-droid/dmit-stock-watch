import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "dmit_watch", Path(__file__).resolve().parents[1] / "dmit_watch.py"
)
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)


def html(status, minutes=14, product="LAX.AS3.Pro.TINY", price="$10.90"):
    return (f"<html><body><div>{status}</div><h3>DMIT · {product}</h3>"
            "<div>CPU 1 vCores内存2.0GB硬盘20GB SSD端口1Gbps流量1000G</div>"
            f"<div>CN2 GIA Premium美国 • 洛杉矶 · CN2 GIA，Premium{price} USD / 月</div>"
            f"<span>上次补货 61 天前✓ {minutes} 分钟前确认</span></body></html>")


class ParseStock(unittest.TestCase):
    def test_out(self):
        self.assertEqual(w.parse_stock(html("缺货")), "out")

    def test_in(self):
        self.assertEqual(w.parse_stock(html("现货")), "in")

    def test_stale(self):
        self.assertEqual(w.parse_stock(html("现货", minutes=72)), "unknown")

    def test_wrong_product(self):
        self.assertEqual(w.parse_stock(html("现货", product="LAX.AS3.EB.TINY")), "unknown")

    def test_wrong_price(self):
        self.assertEqual(w.parse_stock(html("现货", price="$12.90")), "unknown")

    def test_duplicate(self):
        self.assertEqual(w.parse_stock(html("现货") + html("现货")), "unknown")

    def test_missing(self):
        self.assertEqual(w.parse_stock("<h1>DMIT</h1>"), "unknown")

    def test_sct_url(self):
        self.assertEqual(
            w.sender_url("SCTabc"), "https://sctapi.ftqq.com/SCTabc.send"
        )

    def test_sctp_url(self):
        self.assertEqual(
            w.sender_url("sctp123tabc"),
            "https://123.push.ft07.com/send/sctp123tabc.send",
        )


if __name__ == "__main__":
    unittest.main()
