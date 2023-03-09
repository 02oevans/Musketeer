import tkinter.ttk as ttk
from tkinter import font

import numpy as np
from numpy import ma

from . import moduleFrame
from .scrolledFrame import ScrolledFrame
from .table import ButtonFrame, Table, WrappedLabel

DEFAULT_INITIAL_GUESS = 1000


class EquilibriumConstants(moduleFrame.Strategy):
    requiredAttributes = (
        "kNames",
        "knownKs",
        "initialKs",
    )

    # TODO: Either properly save masked arrays, or remove them from the codebase.
    @property
    def knownKs(self):
        return self._knownKs

    @knownKs.setter
    def knownKs(self, value):
        if not isinstance(value, ma.MaskedArray):
            value = ma.masked_invalid(value)
        self._knownKs = value

    @property
    def initialKs(self):
        return self._initialKs

    @initialKs.setter
    def initialKs(self, value):
        if not isinstance(value, ma.MaskedArray):
            value = ma.masked_invalid(value)
        self._initialKs = value

    @property
    def outputNames(self):
        return self.titration.speciation.variableNames

    @property
    def knownMask(self):
        return ma.getmaskarray(self.knownKs)

    @property
    def variableNames(self):
        return self.kNames[self.knownMask]

    @property
    def variableInitialGuesses(self):
        return self.initialKs[self.knownMask].filled(DEFAULT_INITIAL_GUESS)

    def run(self, kVars):
        ks = self.knownKs.copy()
        ks[self.knownMask] = kVars
        return ks


class GetKsAll(EquilibriumConstants):
    # when every equilibrium constant is unknown and independent
    @property
    def kNames(self):
        return self.titration.speciation.variableNames

    @property
    def knownKs(self):
        return ma.array(np.empty(self.outputCount), mask=True)

    @property
    def initialKs(self):
        return ma.array(np.empty(self.outputCount), mask=True)


# TODO: make trimerIndices work with polymers
class GetKsNonspecific(EquilibriumConstants):
    @property
    def kNames(self):
        return self.titration.speciation.variableNames

    @property
    def knownKs(self):
        knownKs = ma.masked_array(np.empty(self.outputCount))
        knownKs[self.trimerIndices] = 0.001
        knownKs[~self.trimerIndices] = ma.masked
        return knownKs

    @property
    def initialKs(self):
        return ma.array(np.empty(self.outputCount), mask=True)


class CustomKsTable(Table):
    def __init__(self, master, titration):
        self.titration = titration
        self.outputNames = self.titration.speciation.variableNames

        if hasattr(titration.equilibriumConstants, "ksMatrix") and (
            titration.equilibriumConstants.ksMatrix.shape
            == (
                len(titration.equilibriumConstants.kNames),
                len(self.outputNames),
            )
        ):
            kNames = titration.equilibriumConstants.kNames
            ksMatrix = titration.equilibriumConstants.ksMatrix
        else:
            kNames = self.outputNames.copy()
            ksMatrix = np.identity(len(self.outputNames), dtype=int)

        columnTitles = np.append(self.outputNames, "Value")
        self.width = max([len(title) for title in columnTitles] + [14]) + 1

        super().__init__(
            master,
            0,
            0,
            columnTitles,
            allowGuesses=True,
            rowOptions=("titles", "new", "delete"),
            columnOptions=("readonlyTitles",),
            boldTitles=True,
            callback=self.createLabels,
        )
        self.readonlyEntry(
            self.headerCells - 1, 1, "Global K for:", font=self.titleFont
        )
        self.addConstantsRow()
        for name, contributions, knownK, initialK in zip(
            kNames,
            ksMatrix,
            titration.equilibriumConstants.knownKs,
            titration.equilibriumConstants.initialKs,
        ):
            if knownK is not ma.masked:
                value = f"{knownK:g}"
            elif initialK is not ma.masked:
                value = f"~{initialK:g}"
            else:
                value = ""
            self.addRow(name, np.append(contributions, value))

    def newRow(self):
        defaultEntries = np.full(self.dataCells.shape[1], "0")
        defaultEntries[-1] = ""
        self.addRow("New variable", defaultEntries)

    def addConstantsRow(self):
        if (
            hasattr(self.titration.equilibriumConstants, "statisticalFactors")
            and len(self.titration.equilibriumConstants.statisticalFactors)
            == len(self.columnTitles) - 1
        ):
            statisticalFactors = self.titration.equilibriumConstants.statisticalFactors
        else:
            statisticalFactors = np.full(len(self.columnTitles) - 1, "1")
        # Value column doesn't have a statistical factor
        statisticalFactors = np.append(statisticalFactors, "")
        oldRowOptions = self.rowOptions
        self.rowOptions = ("readonlyTitles",)
        self.addRow("Statistical factor", statisticalFactors)
        self.rowOptions = oldRowOptions

        # Value column doesn't have a statistical factor
        self.cells[-1, -1].configure(style="TLabel", takefocus=False)
        self.cells[-1, -1].state(["readonly"])

    def createLabels(self, *args, **kwargs):
        try:
            labels = []
            trans = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
            variables = self.rowTitles[1:]
            for globalK, statFactor, variableFactors in zip(
                self.columnTitles[:-1],
                self.data[0, :-1],
                self.data[1:, :-1].T.astype(int),
            ):
                label = f"Global K for {globalK} = {statFactor}"
                for variable, factor in zip(variables, variableFactors):
                    if factor == 0 or factor == "":
                        continue
                    label += f" × {variable}"
                    if factor == 1:
                        continue
                    label += str(factor).translate(trans)
                labels.append(label)
            self.equationsLabel.configure(text="\n".join(labels))
        except Exception:
            pass
        return True

    def convertData(self, string):
        return string


class CustomKsPopup(moduleFrame.Popup):
    def __init__(self, titration, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.titration = titration
        self.title("Enter relationships between Ks")

        height = int(self.master.winfo_height() * 0.4)
        self.frame = ttk.Frame(self, height=height)
        self.frame.pack(expand=True, fill="both")

        customKsLabel = WrappedLabel(
            self.frame,
            text=(
                "Each row represents a variable that will be optimised. The global K"
                " for each complex is the product of a statistical factor and all the"
                " variables raised to the exponent specified in the cells.\n\nIn the"
                " final column, specify a value to fix the variable, leave empty to"
                " optimise the variable, or write ~number to provide an initial guess"
                " for the optimisation."
            ),
            padding=5,
        )
        customKsLabel.pack(expand=False, fill="both")

        scrolledFrame = ScrolledFrame(self.frame, max_width=1500)
        scrolledFrame.pack(expand=True, fill="both")

        self.innerFrame = scrolledFrame.display_widget(ttk.Frame, stretch=True)

        self.customKsTable = CustomKsTable(self.innerFrame, titration)
        self.customKsTable.pack(expand=True, fill="both")

        self.labelFont = font.nametofont("TkTextFont").copy()
        self.labelFont["size"] = int(1.3 * self.labelFont["size"])

        self.equationsLabel = ttk.Label(
            self.frame, anchor="center", font=self.labelFont, padding=5
        )
        self.equationsLabel.pack(fill="both")
        self.customKsTable.equationsLabel = self.equationsLabel
        self.customKsTable.createLabels()

        buttonFrame = ButtonFrame(self.frame, self.reset, self.saveData, self.destroy)
        buttonFrame.pack(expand=False, fill="both", side="bottom")

    def reset(self):
        self.customKsTable.destroy()
        self.customKsTable = CustomKsTable(self.innerFrame, self.titration)
        self.customKsTable.pack(expand=True, fill="both")
        self.customKsTable.label = self.equationsLabel
        self.customKsTable.createLabels()

    def saveData(self):
        self.statisticalFactors = self.customKsTable.data[0, :-1].astype(int)
        self.kNames = self.customKsTable.rowTitles[1:]
        self.ksMatrix = self.customKsTable.data[1:, :-1].astype(int)

        kCells = self.customKsTable.data[1:, -1]
        self.knownKs = ma.array(
            [
                ma.masked if kCell == "" or kCell.startswith("~") else float(kCell)
                for kCell in kCells
            ]
        )
        self.initialKs = ma.array(
            [
                float(kCell[1:]) if kCell.startswith("~") else ma.masked
                for kCell in kCells
            ]
        )

        self.saved = True
        self.destroy()


# TODO: convert to new format
class GetKsCustom(EquilibriumConstants):
    Popup = CustomKsPopup

    popupAttributes = (
        "ksMatrix",
        "statisticalFactors",
        "kNames",
        "knownKs",
        "initialKs",
    )

    def run(self, kVars):
        # microKs as a column vector, with the unknown values filled in
        microKs = self.knownKs.copy()
        microKs[self.knownMask] = kVars
        microKs = np.atleast_2d(microKs).T

        # perform the calculation as previewed in the popup
        globalKs = self.statisticalFactors * np.prod(microKs**self.ksMatrix, 0)
        return globalKs


class KnownKsTable(Table):
    def __init__(self, master, titration):
        self.titration = titration
        super().__init__(
            master,
            0,
            0,
            ["Value"],
            rowOptions=("readonlyTitles",),
            columnOptions=("readonlyTitles",),
            allowGuesses=True,
        )
        self.outputNames = self.titration.speciation.variableNames
        self.populateDefault()

    def populateDefault(self):
        # TODO: knownKs and initialKs should be dicts or structured arrays, in order to
        # still work if the required number of outputs changes
        if len(self.outputNames) != len(self.titration.equilibriumConstants.knownKs):
            for name in self.outputNames:
                self.addRow(name, [""])
            return

        for name, knownK, initialK in zip(
            self.outputNames,
            self.titration.equilibriumConstants.knownKs,
            self.titration.equilibriumConstants.initialKs,
        ):
            if knownK is not ma.masked:
                value = f"{knownK:g}"
            elif initialK is not ma.masked:
                value = f"~{initialK:g}"
            else:
                value = ""
            self.addRow(name, [value])

    def convertData(self, string):
        return string


class KnownKsPopup(moduleFrame.Popup):
    def __init__(self, titration, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.titration = titration
        self.title("Enter known equilibrium constants")

        height = int(self.master.winfo_height() * 0.4)
        frame = ScrolledFrame(self, height=height, max_width=1500)
        frame.pack(expand=True, fill="both")

        innerFrame = frame.display_widget(ttk.Frame, stretch=True)
        knownKsLabel = WrappedLabel(
            innerFrame,
            text=(
                "Enter known K values, leave empty to optimise the value, or write"
                " ~number to provide an initial guess for the optimisation."
            ),
            padding=5,
        )
        knownKsLabel.pack(expand=False, fill="both")

        self.knownKsTable = KnownKsTable(innerFrame, titration)
        self.knownKsTable.pack(expand=True, fill="both")

        buttonFrame = ButtonFrame(innerFrame, self.reset, self.saveData, self.destroy)
        buttonFrame.pack(expand=False, fill="both", side="bottom")

    def reset(self):
        self.knownKsTable.resetData()
        self.knownKsTable.columnTitles = ["Value"]
        self.knownKsTable.populateDefault()

    def saveData(self):
        kCells = self.knownKsTable.data[:, 0]

        self.knownKs = ma.array(
            [
                ma.masked if kCell == "" or kCell.startswith("~") else float(kCell)
                for kCell in kCells
            ]
        )
        self.initialKs = ma.array(
            [
                float(kCell[1:]) if kCell.startswith("~") else ma.masked
                for kCell in kCells
            ]
        )

        self.saved = True
        self.destroy()


class GetKsKnown(EquilibriumConstants):
    Popup = KnownKsPopup
    popupAttributes = ("knownKs", "initialKs")

    @property
    def kNames(self):
        return self.titration.speciation.variableNames


class ModuleFrame(moduleFrame.ModuleFrame):
    group = "Equilibria"
    dropdownLabelText = "Fix any K values?"
    dropdownOptions = {
        "No, optimise all Ks": GetKsAll,
        # "Assume second binding weak": GetKsNonspecific,
        "Fix some known Ks": GetKsKnown,
        "Custom": GetKsCustom,
    }
    attributeName = "equilibriumConstants"
