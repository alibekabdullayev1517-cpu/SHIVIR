from core.safety.filter import Category, Severity, analyze


def test_clean_message_has_no_categories():
    result = analyze("Salom, ishlaring qalay? Sen ajoyibsan!")
    assert result.categories == set()
    assert result.severity == Severity.NONE
    assert not result.should_warn


def test_threat_keyword_triggers_l3():
    result = analyze("seni o'ldiraman")
    assert Category.THREAT in result.categories
    assert result.should_warn
    assert result.severity == Severity.L3


def test_russian_threat_keyword_detected():
    result = analyze("я тебя убью завтра")
    assert Category.THREAT in result.categories
    assert result.severity == Severity.L3


def test_harassment_keyword_is_l2():
    result = analyze("sen ahmoqsan")
    assert Category.HARASSMENT in result.categories
    assert result.severity == Severity.L2


def test_repeated_urls_flagged_as_spam():
    result = analyze("http://a.com http://b.com http://c.com check these out")
    assert Category.SPAM in result.categories
    assert result.severity == Severity.L1


def test_excessive_caps_flagged_as_spam():
    result = analyze("THIS IS A VERY LOUD MESSAGE SHOUTED AT YOU RIGHT NOW")
    assert Category.SPAM in result.categories


def test_sexual_keyword_scores_high_enough_to_warn():
    result = analyze("bu porno video")
    assert Category.SEXUAL in result.categories
    assert result.should_warn
