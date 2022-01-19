# pylint: disable=missing-docstring
import unittest
from typing import Type
from unittest.mock import Mock, patch

import numpy as np
from AnyQt.QtCore import QPointF, Qt
from AnyQt.QtWidgets import QToolTip

from Orange.base import Learner
from Orange.classification import RandomForestLearner, CalibratedLearner, \
    ThresholdLearner
from Orange.data import Table
from Orange.regression import RandomForestRegressionLearner
from Orange.tests.test_classification import all_learners as all_cls_learners
from Orange.tests.test_regression import all_learners as all_reg_learners, \
    init_learner as init_reg_learner
from Orange.widgets.tests.utils import simulate
from orangecontrib.explain.explainer import INSTANCE_ORDERINGS
from orangecontrib.explain.widgets.owexplainpredictions import ForcePlot, \
    OWExplainPredictions
from orangewidget.tests.base import WidgetTest


def init_learner(learner: Type[Learner], table: Table) -> Learner:
    if learner in (CalibratedLearner, ThresholdLearner):
        return CalibratedLearner(RandomForestLearner())
    return init_reg_learner(learner, table)


class TestForcePlot(WidgetTest):
    def setUp(self):
        widget = self.create_widget(OWExplainPredictions)
        self.plot = ForcePlot(widget)
        self.housing = Table("housing")

    def test_zoom_select(self):
        self.plot.select_button_clicked()
        self.plot.pan_button_clicked()
        self.plot.zoom_button_clicked()
        self.plot.reset_button_clicked()

    def test_selection(self):
        selection_handler = Mock()

        view_box = self.plot.getViewBox()
        self.plot.selectionChanged.connect(selection_handler)

        event = Mock()
        event.button.return_value = Qt.LeftButton
        event.buttonDownPos.return_value = QPointF(10, 0)
        event.pos.return_value = QPointF(30, 0)
        event.isFinish.return_value = True

        # select before data is sent
        view_box.mouseDragEvent(event)

        # set data
        x_data = np.arange(5)
        pos_y_data = [(np.arange(5) - 1, np.arange(5))]
        neg_y_data = [(np.arange(5), np.arange(5) + 1)]
        self.plot.set_data(x_data, pos_y_data, neg_y_data, self.housing, None)

        # select after data is sent
        view_box.mouseDragEvent(event)
        selection_handler.assert_called_once()

        # select other instances
        event.buttonDownPos.return_value = QPointF(40, 0)
        event.pos.return_value = QPointF(60, 0)

        selection_handler.reset_mock()
        view_box.mouseDragEvent(event)
        selection_handler.assert_called_once()
        self.assertEqual(len(selection_handler.call_args[0][0]), 2)

        # click on the plot resets selection
        selection_handler.reset_mock()
        view_box.mouseClickEvent(event)
        selection_handler.assert_called_once()
        self.assertEqual(len(selection_handler.call_args[0][0]), 0)

    @patch.object(QToolTip, "showText")
    def test_tooltip(self, show_text: Mock):
        event = Mock()
        point = self.plot.getViewBox().mapViewToScene(QPointF(1, 2))
        event.scenePos.return_value = point
        self.plot.help_event(event)
        self.assertIsNone(show_text.call_args)

        x_data = np.arange(5)
        pos_y_data = [(np.arange(5) - 1, np.arange(5))]
        neg_y_data = [(np.arange(5), np.arange(5) + 1)]
        self.plot.set_data(x_data, pos_y_data, neg_y_data,
                           self.housing[:5, :2], None)

        event = Mock()
        point = self.plot.getViewBox().mapViewToScene(QPointF(1, 2))
        event.scenePos.return_value = point
        self.plot.help_event(event)
        self.assertEqual(
            show_text.call_args[0][1],
            "<br/><br/><b>Features</b>:<br/>CRIM = 0.02731<br/>ZN = 0.0"
        )

        self.plot.set_data(self.housing.X[:5, 0], pos_y_data, neg_y_data,
                           self.housing[:5, :2], self.housing.domain[0])

        event = Mock()
        point = self.plot.getViewBox().mapViewToScene(QPointF(1, 2))
        event.scenePos.return_value = point
        self.plot.help_event(event)
        self.assertEqual(
            show_text.call_args[0][1],
            "<br/><br/><b>Features</b>:<br/>CRIM = 0.06905<br/>ZN = 0.0"
        )

    def test_instance_tooltip(self):
        domain = self.housing.domain
        instance = self.housing[0]
        text = "<b>Class</b>:<br/>MEDV = 24.0<br/><br/><b>Features</b>:<br/>" \
               "CRIM = 0.00632<br/>ZN = 18.0<br/>INDUS = 2.31<br/>CHAS = 0" \
               "<br/>NOX = 0.5380<br/>RM = 6.575<br/>AGE = 65.2<br/>" \
               "DIS = 4.0900<br/>RAD = 1<br/>... and 4 others"
        self.assertEqual(self.plot._instance_tooltip(domain, instance), text)


class TestOWExplainPredictions(WidgetTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.heart = Table("heart_disease")
        cls.housing = Table("housing")
        kwargs = {"random_state": 0}
        cls.rf_cls = RandomForestLearner(**kwargs)(cls.heart)
        cls.rf_reg = RandomForestRegressionLearner(**kwargs)(cls.housing)

    def setUp(self):
        self.widget = self.create_widget(OWExplainPredictions)

    def test_classification_data_classification_model(self):
        self.send_signal(self.widget.Inputs.background_data, self.heart)
        self.send_signal(self.widget.Inputs.data, self.heart[:10])
        self.send_signal(self.widget.Inputs.model, self.rf_cls)
        self.wait_until_finished()
        self.assertPlotNotEmpty(self.widget.graph)

    def test_classification_data_regression_model(self):
        self.send_signal(self.widget.Inputs.background_data, self.heart)
        self.send_signal(self.widget.Inputs.data, self.heart[:10])
        self.send_signal(self.widget.Inputs.model, self.rf_reg)
        self.wait_until_finished()
        self.assertPlotEmpty(self.widget.graph)
        self.assertTrue(self.widget.Error.domain_transform_err.is_shown())

    def test_regression_data_regression_model(self):
        self.send_signal(self.widget.Inputs.background_data, self.housing)
        self.send_signal(self.widget.Inputs.data, self.housing[:1])
        self.send_signal(self.widget.Inputs.model, self.rf_reg)
        self.wait_until_finished()
        self.assertPlotNotEmpty(self.widget.graph)

    def test_regression_data_classification_model(self):
        self.send_signal(self.widget.Inputs.background_data, self.housing)
        self.send_signal(self.widget.Inputs.data, self.housing[:1])
        self.send_signal(self.widget.Inputs.model, self.rf_cls)
        self.wait_until_finished()
        self.assertPlotEmpty(self.widget.graph)
        self.assertTrue(self.widget.Error.domain_transform_err.is_shown())

    def test_target_combo(self):
        self.assertEqual(self.widget._target_combo.currentText(), "")
        self.assertTrue(self.widget._target_combo.isEnabled())

        self.send_signal(self.widget.Inputs.model, self.rf_cls)
        self.assertEqual(self.widget._target_combo.currentText(), "0")
        self.assertTrue(self.widget._target_combo.isEnabled())

        self.send_signal(self.widget.Inputs.model, self.rf_reg)
        self.assertEqual(self.widget._target_combo.currentText(), "")
        self.assertFalse(self.widget._target_combo.isEnabled())

        self.send_signal(self.widget.Inputs.model, self.rf_cls)
        self.assertEqual(self.widget._target_combo.currentText(), "0")
        self.assertTrue(self.widget._target_combo.isEnabled())

        self.send_signal(self.widget.Inputs.model, self.rf_reg)
        self.assertEqual(self.widget._target_combo.currentText(), "")
        self.assertFalse(self.widget._target_combo.isEnabled())

        self.send_signal(self.widget.Inputs.model, None)
        self.assertEqual(self.widget._target_combo.currentText(), "")
        self.assertTrue(self.widget._target_combo.isEnabled())

    def test_order_combo(self):
        self.assertEqual(self.widget._order_combo.currentText(),
                         "Original instance ordering")
        self.assertEqual(self.widget._order_combo.count(), 3)

        self.send_signal(self.widget.Inputs.model, self.rf_cls)
        self.assertEqual(self.widget._order_combo.currentText(),
                         "Original instance ordering")
        # 1 separator
        self.assertEqual(self.widget._order_combo.count(),
                         len(self.rf_cls.domain.attributes) + 1 +
                         len(INSTANCE_ORDERINGS))
        self.send_signal(self.widget.Inputs.background_data, self.heart)
        self.send_signal(self.widget.Inputs.data, self.heart[:10])
        self.wait_until_finished()
        simulate.combobox_run_through_all(self.widget._order_combo)

        self.send_signal(self.widget.Inputs.model, None)
        self.assertEqual(self.widget._order_combo.currentText(),
                         "Original instance ordering")
        self.assertEqual(self.widget._order_combo.count(), 3)

    def test_annotation_combo(self):
        self.assertEqual(self.widget._annot_combo.currentText(), "Enumeration")
        self.assertEqual(self.widget._annot_combo.count(), 1)

        self.send_signal(self.widget.Inputs.model, self.rf_reg)
        self.assertEqual(self.widget._annot_combo.currentText(), "Enumeration")
        self.assertEqual(self.widget._annot_combo.count(), 1)

        self.send_signal(self.widget.Inputs.background_data, self.heart)
        self.send_signal(self.widget.Inputs.data, self.heart[:5])
        self.send_signal(self.widget.Inputs.model, self.rf_cls)
        self.assertEqual(self.widget._annot_combo.currentText(), "Enumeration")
        self.assertEqual(self.widget._annot_combo.count(), 3)
        self.wait_until_finished()

        self.widget.graph.set_axis = Mock()
        simulate.combobox_activate_index(self.widget._annot_combo, 2)
        args = ([[(0, "0"), (1, "1"), (2, "1"), (3, "0"), (4, "0")]], True)
        self.widget.graph.set_axis.assert_called_once_with(*args)

        self.widget.graph.set_axis.reset_mock()
        simulate.combobox_activate_index(self.widget._annot_combo, 0)
        args = (None, False)
        self.widget.graph.set_axis.assert_called_once_with(*args)

        self.send_signal(self.widget.Inputs.model, None)
        self.assertEqual(self.widget._annot_combo.currentText(), "Enumeration")
        self.assertEqual(self.widget._annot_combo.count(), 1)

    def test_setup_plot(self):
        self.widget.graph.set_data = Mock()
        self.widget.graph.set_axis = Mock()

        self.send_signal(self.widget.Inputs.background_data, self.heart)
        self.send_signal(self.widget.Inputs.data, self.heart[:5])
        self.send_signal(self.widget.Inputs.model, self.rf_cls)
        self.wait_until_finished()

        simulate.combobox_activate_index(self.widget._annot_combo, 2)
        self.widget.graph.set_data.assert_called_once()
        args = ([[(0, "0"), (1, "1"), (2, "1"), (3, "0"), (4, "0")]], True)
        self.widget.graph.set_axis.assert_called_once_with(*args)

        self.widget.graph.set_data.reset_mock()
        self.widget.graph.set_axis.reset_mock()
        simulate.combobox_activate_index(self.widget._order_combo, 4)
        self.widget.graph.set_data.assert_called_once()
        args = ([[(0, "0"), (1, "0"), (2, "0"), (3, "1"), (4, "1")]], True)
        self.widget.graph.set_axis.assert_called_once_with(*args)

    def test_plot(self):
        self.send_signal(self.widget.Inputs.data, self.heart)
        self.assertPlotEmpty(self.widget.graph)

        self.send_signal(self.widget.Inputs.background_data, self.heart)
        self.send_signal(self.widget.Inputs.model, self.rf_cls)
        self.wait_until_finished()
        self.assertPlotNotEmpty(self.widget.graph)

        self.send_signal(self.widget.Inputs.model, None)
        self.assertPlotEmpty(self.widget.graph)

        self.send_signal(self.widget.Inputs.model, self.rf_reg)
        self.wait_until_finished()
        self.assertPlotEmpty(self.widget.graph)

        self.send_signal(self.widget.Inputs.data, self.heart)
        self.wait_until_finished()
        self.assertPlotEmpty(self.widget.graph)

        self.send_signal(self.widget.Inputs.model, self.rf_cls)
        self.wait_until_finished()
        self.assertPlotNotEmpty(self.widget.graph)

        self.send_signal(self.widget.Inputs.data, None)
        self.assertPlotEmpty(self.widget.graph)

    def test_plot_multiple_selection(self):
        self.send_signal(self.widget.Inputs.data, self.heart[:10])
        self.send_signal(self.widget.Inputs.background_data, self.heart)
        self.send_signal(self.widget.Inputs.model, self.rf_cls)
        self.wait_until_finished()

        event = Mock()
        event.button.return_value = Qt.LeftButton
        event.buttonDownPos.return_value = QPointF(10, 0)
        event.pos.return_value = QPointF(30, 0)
        event.isFinish.return_value = True
        self.widget.graph.getViewBox().mouseDragEvent(event)

        output = self.get_output(self.widget.Outputs.selected_data)
        self.assertEqual(len(output), 4)

        event.buttonDownPos.return_value = QPointF(40, 0)
        event.pos.return_value = QPointF(50, 0)
        self.widget.graph.getViewBox().mouseDragEvent(event)

        output = self.get_output(self.widget.Outputs.selected_data)
        self.assertEqual(len(output), 5)

    def test_all_models(self):
        def run(data):
            self.send_signal(self.widget.Inputs.background_data, data)
            self.send_signal(self.widget.Inputs.data, data)
            model = init_learner(learner, data)(data)
            self.send_signal(self.widget.Inputs.model, model)
            self.wait_until_finished(timeout=50000)

        for learner in all_reg_learners():
            run(self.housing[::4])
        for learner in all_cls_learners():
            run(self.heart[::4])

    def test_output_scores(self):
        self.send_signal(self.widget.Inputs.data, self.heart[:10])
        self.send_signal(self.widget.Inputs.background_data, self.heart)
        self.send_signal(self.widget.Inputs.model, self.rf_cls)
        self.wait_until_finished()

        output = self.get_output(self.widget.Outputs.scores)
        self.assertIsInstance(output, Table)
        self.assertEqual(len(output), 10)
        self.assertEqual(output.X.shape[1], len(self.rf_cls.domain.attributes))
        self.assertEqual(len(output.Y), 10)

        self.send_signal(self.widget.Inputs.model, None)
        self.assertIsNone(self.get_output(self.widget.Outputs.scores))

    def test_output_selection(self):
        self.send_signal(self.widget.Inputs.data, self.heart[:10])
        self.send_signal(self.widget.Inputs.background_data, self.heart)
        self.send_signal(self.widget.Inputs.model, self.rf_cls)
        self.wait_until_finished()

        event = Mock()
        event.button.return_value = Qt.LeftButton
        event.buttonDownPos.return_value = QPointF(10, 0)
        event.pos.return_value = QPointF(30, 0)
        event.isFinish.return_value = True
        self.widget.graph.getViewBox().mouseDragEvent(event)

        output = self.get_output(self.widget.Outputs.selected_data)
        self.assertIsInstance(output, Table)
        self.assertEqual(len(output), 4)

        self.send_signal(self.widget.Inputs.model, None)
        self.assertIsNone(self.get_output(self.widget.Outputs.selected_data))

    def test_output_data(self):
        self.send_signal(self.widget.Inputs.data, self.heart[:10])
        self.send_signal(self.widget.Inputs.background_data, self.heart)
        self.send_signal(self.widget.Inputs.model, self.rf_cls)
        self.wait_until_finished()

        output = self.get_output(self.widget.Outputs.annotated_data)
        self.assertIsInstance(output, Table)
        self.assertEqual(len(output), 10)

        self.send_signal(self.widget.Inputs.model, None)
        output = self.get_output(self.widget.Outputs.annotated_data)
        self.assertIsInstance(output, Table)

        self.send_signal(self.widget.Inputs.background_data, None)
        output = self.get_output(self.widget.Outputs.annotated_data)
        self.assertIsInstance(output, Table)

        self.send_signal(self.widget.Inputs.data, None)
        self.assertIsNone(self.get_output(self.widget.Outputs.annotated_data))

    def test_settings(self):
        self.send_signal(self.widget.Inputs.data, self.heart[:10])
        self.send_signal(self.widget.Inputs.background_data, self.heart)
        self.send_signal(self.widget.Inputs.model, self.rf_cls)

        simulate.combobox_activate_index(self.widget._target_combo, 1)
        simulate.combobox_activate_index(self.widget._order_combo, 4)
        simulate.combobox_activate_index(self.widget._annot_combo, 2)

        self.send_signal(self.widget.Inputs.data, self.housing[:10])
        self.send_signal(self.widget.Inputs.background_data, self.housing)
        self.send_signal(self.widget.Inputs.model, self.rf_reg)

        self.assertEqual(self.widget.target_index, -1)
        self.assertEqual(self.widget.order_index, 0)
        self.assertEqual(self.widget.annot_index, 0)

        self.send_signal(self.widget.Inputs.data, self.heart[:10])
        self.send_signal(self.widget.Inputs.background_data, self.heart)
        self.send_signal(self.widget.Inputs.model, self.rf_cls)

        self.assertEqual(self.widget.target_index, 1)
        self.assertEqual(self.widget.order_index, 4)
        self.assertEqual(self.widget.annot_index, 2)

    def test_saved_selection(self):
        self.send_signal(self.widget.Inputs.data, self.heart[:10])
        self.send_signal(self.widget.Inputs.background_data, self.heart)
        self.send_signal(self.widget.Inputs.model, self.rf_cls)
        self.wait_until_finished()

        event = Mock()
        event.button.return_value = Qt.LeftButton
        event.buttonDownPos.return_value = QPointF(10, 0)
        event.pos.return_value = QPointF(30, 0)
        event.isFinish.return_value = True
        self.widget.graph.getViewBox().mouseDragEvent(event)

        event.buttonDownPos.return_value = QPointF(40, 0)
        event.pos.return_value = QPointF(50, 0)
        self.widget.graph.getViewBox().mouseDragEvent(event)

        output = self.get_output(self.widget.Outputs.selected_data)
        self.assertEqual(len(output), 5)

        settings = self.widget.settingsHandler.pack_data(self.widget)

        w = self.create_widget(OWExplainPredictions, stored_settings=settings)
        self.send_signal(w.Inputs.data, self.heart[:10], widget=w)
        self.send_signal(w.Inputs.background_data, self.heart, widget=w)
        self.send_signal(w.Inputs.model, self.rf_cls, widget=w)
        self.wait_until_finished()

        output = self.get_output(w.Outputs.selected_data, widget=w)
        self.assertEqual(len(output), 5)

    def test_visual_settings(self):
        self.assertEqual(True, False)

    def test_send_report(self):
        self.widget.send_report()
        self.send_signal(self.widget.Inputs.data, self.heart[:10])
        self.send_signal(self.widget.Inputs.background_data, self.heart)
        self.send_signal(self.widget.Inputs.model, self.rf_cls)
        self.widget.send_report()
        self.send_signal(self.widget.Inputs.data, self.housing[:10])
        self.send_signal(self.widget.Inputs.background_data, self.housing)
        self.send_signal(self.widget.Inputs.model, self.rf_reg)
        self.widget.send_report()

    def assertPlotNotEmpty(self, plot: ForcePlot):
        self.assertGreater(len(plot.plotItem.items), 0)

    def assertPlotEmpty(self, plot: ForcePlot):
        self.assertEqual(len(plot.plotItem.items), 0)


if __name__ == "__main__":
    unittest.main()
