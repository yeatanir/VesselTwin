import pytest
from llm.excerpt_match import supports, numbers

pytestmark = pytest.mark.vessel("llm")
CH = "10 sccm to 160 sccm (then higher)"


def test_known_answer_pass():
    assert supports("s01", CH, "While the gas flow rate was 10 sccm, the nucleation density was low.")["verified"]


def test_value_within_2pct_and_unit_conversion():
    assert supports("s01", CH, "the carrier gas flow rate of 163 sccm")["verified"]          # +1.9%
    assert not supports("s01", CH, "the carrier gas flow rate of 165 sccm")["verified"]      # +3.1%
    assert supports("s01", CH, "gas flow rate 160 mL/min")["verified"]                        # mL/min == sccm here
    assert supports("s13", "750 C to 800 C", "the growth temperature of 1073 K")["verified"]   # 800 C in kelvin


def test_name_alone_or_value_alone_fails():
    assert not supports("s01", CH, "the gas flow rate strongly affects nucleation")["verified"]
    assert not supports("s01", CH, "samples were annealed at 160 sccm")["verified"]
    assert not supports("s01", CH, "the gas flow rate was 10 mg")["verified"]                  # dimension mismatch


def test_bare_numbers_inherit_next_unit():
    assert [round(v) for _, v in numbers("650 C to 700, 750, 800 C")] == [923, 973, 1023, 1073]


def test_no_alias_means_unverifiable():
    assert not supports("s99", CH, "gas flow rate 10 sccm")["verified"]
