import sys
import unittest

from qtpy.QtCore import Qt
from qtpy.QtGui import QDoubleValidator, QIntValidator
from qtpy.QtTest import QSignalSpy, QTest
from qtpy.QtWidgets import QApplication

from view.widgets.base_device_widget import BaseDeviceWidget
from view.widgets.miscellaneous_widgets.q_scrollable_line_edit import QScrollableLineEdit

app = QApplication(sys.argv)


class BaseDeviceWidgetTests(unittest.TestCase):
    """_summary_"""

    def test_string_properties(self):
        """_summary_"""
        properties = {"test_string": "hello"}
        widget = BaseDeviceWidget(properties, properties)

        self.assertTrue(hasattr(widget, "test_string"))
        self.assertTrue(widget.test_string == "hello")
        self.assertTrue(hasattr(widget, "test_string_widget"))
        self.assertTrue(type(widget.test_string_widget) == QScrollableLineEdit)
        self.assertTrue(widget.test_string_widget.text() == "hello")

        # change value externally
        outside_signal_spy = QSignalSpy(widget.ValueChangedOutside)
        widget.test_string = "howdy"
        self.assertEqual(len(outside_signal_spy), 1)  # triggered once
        self.assertTrue(outside_signal_spy.isValid())
        self.assertTrue(widget.test_string == "howdy")
        self.assertTrue(widget.test_string_widget.text() == "howdy")

        # change value internally
        inside_signal_spy = QSignalSpy(widget.ValueChangedInside)
        widget.test_string_widget.setText("hello")
        QTest.keyPress(widget.test_string_widget, Qt.Key_Enter)  # press enter
        self.assertEqual(len(inside_signal_spy), 1)  # triggered once
        self.assertTrue(inside_signal_spy.isValid())
        self.assertTrue(widget.test_string == "hello")
        self.assertTrue(widget.test_string_widget.text() == "hello")

    def test_int_properties(self):
        """_summary_"""
        properties = {"test_int": 1}
        widget = BaseDeviceWidget(properties, properties)

        self.assertTrue(hasattr(widget, "test_int"))
        self.assertTrue(widget.test_int == 1)
        self.assertTrue(hasattr(widget, "test_int_widget"))
        self.assertTrue(type(widget.test_int_widget) == QScrollableLineEdit)
        self.assertTrue(type(widget.test_int_widget.validator()) == QIntValidator)
        self.assertTrue(widget.test_int_widget.value() == 1)

        # change value externally
        outside_signal_spy = QSignalSpy(widget.ValueChangedOutside)
        widget.test_int = 0
        self.assertEqual(len(outside_signal_spy), 1)  # triggered once
        self.assertTrue(outside_signal_spy.isValid())
        self.assertTrue(widget.test_int == 0)
        self.assertTrue(widget.test_int_widget.value() == 0)

        # change value internally
        inside_signal_spy = QSignalSpy(widget.ValueChangedInside)
        widget.test_int_widget.setValue(1)
        QTest.keyPress(widget.test_int_widget, Qt.Key_Enter)  # press enter
        self.assertEqual(len(inside_signal_spy), 1)  # triggered once
        self.assertTrue(inside_signal_spy.isValid())
        self.assertTrue(widget.test_int == 1)
        self.assertTrue(widget.test_int_widget.value() == 1)

    def test_float_properties(self):
        """_summary_"""
        properties = {"test_float": 1.5}
        widget = BaseDeviceWidget(properties, properties)

        self.assertTrue(hasattr(widget, "test_float"))
        self.assertTrue(widget.test_float == 1.5)
        self.assertTrue(hasattr(widget, "test_float_widget"))
        self.assertTrue(type(widget.test_float_widget) == QScrollableLineEdit)
        self.assertTrue(type(widget.test_float_widget.validator()) == QDoubleValidator)
        self.assertTrue(widget.test_float_widget.value() == 1.5)

        # change value externally
        outside_signal_spy = QSignalSpy(widget.ValueChangedOutside)
        widget.test_float = 0.5
        self.assertEqual(len(outside_signal_spy), 1)  # triggered once
        self.assertTrue(outside_signal_spy.isValid())
        self.assertTrue(widget.test_float == 0.5)
        self.assertTrue(widget.test_float_widget.value() == 0.5)

        # change value internally
        inside_signal_spy = QSignalSpy(widget.ValueChangedInside)
        widget.test_float_widget.setValue(1.5)
        QTest.keyPress(widget.test_float_widget, Qt.Key_Enter)  # press enter
        self.assertEqual(len(inside_signal_spy), 1)  # triggered once
        self.assertTrue(inside_signal_spy.isValid())
        self.assertTrue(widget.test_float == 1.5)
        self.assertTrue(widget.test_float_widget.value() == 1.5)

    def test_list_properties(self):
        """_summary_"""
        properties = {"test_list": ["hello", "world"]}
        widget = BaseDeviceWidget(properties, properties)

        self.assertTrue(hasattr(widget, "test_list"))
        self.assertTrue(widget.test_list == ["hello", "world"])

        self.assertTrue(hasattr(widget, "test_list.0"))
        self.assertTrue(getattr(widget, "test_list.0") == "hello")
        self.assertTrue(hasattr(widget, "test_list.0_widget"))
        self.assertTrue(type(getattr(widget, "test_list.0_widget")) == QScrollableLineEdit)
        self.assertTrue(getattr(widget, "test_list.0_widget").text() == "hello")

        self.assertTrue(hasattr(widget, "test_list.1"))
        self.assertTrue(getattr(widget, "test_list.1") == "world")
        self.assertTrue(hasattr(widget, "test_list.1_widget"))
        self.assertTrue(type(getattr(widget, "test_list.1_widget")) == QScrollableLineEdit)
        self.assertTrue(getattr(widget, "test_list.1_widget").text() == "world")

        # change value internally
        getattr(widget, "test_list.0_widget").setText("howdy")
        QTest.keyPress(getattr(widget, "test_list.0_widget"), Qt.Key_Enter)  # press enter
        self.assertTrue(widget.test_list == ["howdy", "world"])
        self.assertTrue(getattr(widget, "test_list.0") == "howdy")

    def test_dict_properties(self):
        """_summary_"""
        properties = {"test_dict": {"greeting": "hello", "directed_to": "world"}}
        widget = BaseDeviceWidget(properties, properties)

        self.assertTrue(hasattr(widget, "test_dict"))
        self.assertTrue(widget.test_dict == {"greeting": "hello", "directed_to": "world"})

        self.assertTrue(hasattr(widget, "test_dict.greeting"))
        self.assertTrue(getattr(widget, "test_dict.greeting") == "hello")
        self.assertTrue(hasattr(widget, "test_dict.greeting_widget"))
        self.assertTrue(type(getattr(widget, "test_dict.greeting_widget")) == QScrollableLineEdit)
        self.assertTrue(getattr(widget, "test_dict.greeting_widget").text() == "hello")

        self.assertTrue(hasattr(widget, "test_dict.directed_to"))
        self.assertTrue(getattr(widget, "test_dict.directed_to") == "world")
        self.assertTrue(hasattr(widget, "test_dict.directed_to_widget"))
        self.assertTrue(type(getattr(widget, "test_dict.directed_to_widget")) == QScrollableLineEdit)
        self.assertTrue(getattr(widget, "test_dict.directed_to_widget").text() == "world")

        # change value internally
        getattr(widget, "test_dict.greeting_widget").setText("howdy")
        QTest.keyPress(getattr(widget, "test_dict.greeting_widget"), Qt.Key_Enter)  # press enter
        self.assertTrue(widget.test_dict == {"greeting": "howdy", "directed_to": "world"})
        self.assertTrue(getattr(widget, "test_dict.greeting") == "howdy")

    def test_nested_properties(self):
        """_summary_"""
        properties = {
            "test_nest_dict": {"greeting_options": {"formal": "hello", "cowboy": "howdy"}, "directed_to": "world"}
        }
        widget = BaseDeviceWidget(properties, properties)

        self.assertTrue(hasattr(widget, "test_nest_dict.greeting_options"))
        self.assertTrue(getattr(widget, "test_nest_dict.greeting_options") == {"formal": "hello", "cowboy": "howdy"})
        self.assertTrue(hasattr(widget, "test_nest_dict.greeting_options"))

        self.assertTrue(hasattr(widget, "test_nest_dict.greeting_options.formal"))
        self.assertTrue(getattr(widget, "test_nest_dict.greeting_options.formal") == "hello")
        self.assertTrue(hasattr(widget, "test_nest_dict.greeting_options.formal_widget"))
        self.assertTrue(type(getattr(widget, "test_nest_dict.greeting_options.formal_widget")) == QScrollableLineEdit)
        self.assertTrue(getattr(widget, "test_nest_dict.greeting_options.formal_widget").text() == "hello")

        self.assertTrue(hasattr(widget, "test_nest_dict.greeting_options.cowboy"))
        self.assertTrue(getattr(widget, "test_nest_dict.greeting_options.cowboy") == "howdy")
        self.assertTrue(hasattr(widget, "test_nest_dict.greeting_options.cowboy_widget"))
        self.assertTrue(type(getattr(widget, "test_nest_dict.greeting_options.cowboy_widget")) == QScrollableLineEdit)
        self.assertTrue(getattr(widget, "test_nest_dict.greeting_options.cowboy_widget").text() == "howdy")

        # change value internally
        getattr(widget, "test_nest_dict.greeting_options.formal_widget").setText("salutations")
        QTest.keyPress(getattr(widget, "test_nest_dict.greeting_options.formal_widget"), Qt.Key_Enter)  # press enter
        self.assertTrue(
            widget.test_nest_dict
            == {"greeting_options": {"formal": "salutations", "cowboy": "howdy"}, "directed_to": "world"}
        )
        self.assertTrue(getattr(widget, "test_nest_dict.greeting_options.formal") == "salutations")


if __name__ == "__main__":
    unittest.main()
