import tkinter as tk
import tkinter.ttk as ttk
import tkinter.messagebox as mb
from decimal import Decimal

import re
import numpy as np

from . import moduleFrame
from .table import Table, ButtonFrame
from .scrolledFrame import ScrolledFrame

prefixesDecimal = {
    "": Decimal(1),
    "m": Decimal(1e-3),
    "u": Decimal(1e-6),
    "μ": Decimal(1e-6),
    "n": Decimal(1e-9)
}

prefixes = dict([key, float(value)] for key, value in prefixesDecimal.items())


class StockTable(Table):
    def __init__(self, master, titration):
        if hasattr(titration, "stockTitles"):
            stockTitles = titration.stockTitles
        else:
            stockTitles = ("Stock 1", "Stock 2")
        super().__init__(master, 2, stockTitles, allowBlanks=True,
                         rowOptions=("readonlyTitles", "delete"),
                         columnOptions=("new", "delete"))

        self.titration = titration

        self.label(0, 0, "Stock concentrations:", 4)
        self.label(1, 2, "Unit:")
        _, self.unit = self.dropdown(1, 3, ("nm", "\u03BCM", "mM", "M"), "mM")

        if hasattr(titration, "stockConcs"):
            self.populate(titration.stockConcs)
        else:
            self.populateDefault()

    def deleteRowButton(self, *args, **kwargs):
        button = super().deleteRowButton(*args, **kwargs)
        button.state(["disabled"])
        return button

    def populate(self, stockConcs):
        for name, row in zip(self.titration.freeNames, stockConcs):
            self.addRow(name, [self.convertConc(conc, "M", self.unit.get())
                               for conc in row])

    def populateDefault(self):
        for name in self.titration.freeNames:
            self.addRow(name)

    def convertConc(self, conc, fromUnit, toUnit):
        if np.isnan(conc):
            return ""
        conc = Decimal(conc)
        convertedConc = float(
            conc * prefixesDecimal[fromUnit.strip("M")]
            / prefixesDecimal[toUnit.strip("M")]
        )
        return f"{convertedConc:g}"  # strip trailing zeroes


class VolumesTable(Table):
    def __init__(self, master, titration):
        if hasattr(titration, "stockTitles"):
            stockTitles = titration.stockTitles
        else:
            stockTitles = ("Stock 1", "Stock 2")
        super().__init__(master, 4, stockTitles, allowBlanks=False,
                         rowOptions=("delete", "readonlyTitles"),
                         columnOptions=())

        self.titration = titration

        self.label(0, 0, "Addition volumes:", 4)
        self.label(1, 2, "Unit:")
        _, self.unit = self.dropdown(
            1, 3, ("nL", "\u03BCL", "mL", "L"), "\u03BCL"
        )
        if hasattr(titration, "volumesUnit"):
            self.unit.set(titration.volumesUnit)

        self.label(3, 1, "Addition title:")

        for stock in range(len(stockTitles)):
            self.cells[0, stock + 2] = self.button(
                self.headerRows, stock + 2, "Copy first",
                lambda stock=stock: self.copyFirst(stock)
            )
            self.cells[1, stock + 2] = self.button(
                self.headerRows + 1, stock + 2, "Copy from titles",
                lambda stock=stock: self.copyFromTitles(stock)
            )

        if hasattr(titration, "volumes"):
            self.populate(titration.volumes)
        else:
            self.populateDefault()

    def populate(self, volumes):
        for name, row in zip(self.titration.additionTitles, volumes):
            self.addRow(name, [self.convertVolume(volume, "L", self.unit.get())
                               for volume in row])

    def populateDefault(self):
        for name in self.titration.additionTitles:
            self.addRow(name)

    def copyFirst(self, dataColumn):
        cells = self.cells[2:, dataColumn + 2]
        first = cells[0].get()
        for cell in cells:
            cell.set(first)

    def copyFromTitles(self, dataColumn):
        cells = self.cells[2:]
        for row in cells:
            title = row[1].get()
            volume = self.getVolumeFromString(title, self.unit.get())
            if volume is not None:
                row[dataColumn + 2].set(volume)

    def OLDcopyFromTitles(self, dataColumn):
        rows, _ = self.cells.shape
        for row in range(rows):
            if self.cells[row, dataColumn + 2] is not None:
                title = self.cells[row, 1].get()
                volume = self.getVolumeFromString(title, self.unit.get())
                if volume is not None:
                    self.cells[row, dataColumn + 2].set(volume)

    def getVolumeFromString(self, string, toUnit="L"):
        searchResult = re.search(r"([0-9.]+) ?([nuμm]?)[lL]", string)
        if not searchResult:
            return None
        volume, prefix = searchResult.group(1, 2)
        return self.convertVolume(volume, prefix, toUnit)

    def convertVolume(self, volume, fromUnit, toUnit):
        volume = Decimal(volume)
        convertedVolume = float(
            volume * prefixesDecimal[fromUnit.strip("L")]
            / prefixesDecimal[toUnit.strip("L")]
        )
        return f"{convertedVolume:g}"  # strip trailing zeroes


class VolumesPopup(tk.Toplevel):
    def __init__(self, titration, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.titration = titration
        self.title("Enter volumes")
        self.grab_set()

        height = int(self.master.winfo_height() * 0.8)
        frame = ScrolledFrame(self, height=height, max_width=1500)
        frame.pack(expand=True, fill="both")
        frame.bind_arrow_keys(self)
        frame.bind_scroll_wheel(self)

        innerFrame = frame.display_widget(ttk.Frame, stretch=True)

        unknownConcsFrame = ttk.Frame(innerFrame, borderwidth=5)
        unknownConcsFrame.pack(expand=True, fill="both")
        unknownConcsLabel = ttk.Label(
            unknownConcsFrame,
            text="Leave cells blank for unknown concentrations."
        )
        unknownConcsLabel.pack()
        self.unknownTotalConcsLinkedVar = tk.BooleanVar()
        if hasattr(titration, "unknownTotalConcsLinked"):
            self.unknownTotalConcsLinkedVar.set(
                self.titration.unknownTotalConcsLinked
            )
        else:
            self.unknownTotalConcsLinkedVar.set(True)
        unknownTotalConcsCheckbutton = ttk.Checkbutton(
            unknownConcsFrame, variable=self.unknownTotalConcsLinkedVar,
            text="Link unknown concentrations for the same species in different stocks"
        )
        unknownTotalConcsCheckbutton.pack()

        self.stockTable = StockTable(innerFrame, titration)
        self.stockTable.pack(expand=True, fill="both")
        self.volumesTable = VolumesTable(innerFrame, titration)
        self.volumesTable.pack(expand=True, fill="both")

        self.stockTable.newColumnButton.configure(command=self.addColumns)
        self.stockTable._deleteColumn = self.stockTable.deleteColumn
        self.stockTable.deleteColumn = self.deleteColumns

        buttonFrame = ButtonFrame(
            innerFrame, self.reset, self.saveData, self.destroy
        )
        buttonFrame.pack(expand=False, fill="both")

    def addColumns(self):
        self.stockTable.addColumn()
        self.volumesTable.addColumn()

    def deleteColumns(self, column):
        self.stockTable._deleteColumn(column)
        self.volumesTable.deleteColumn(column)

    def reset(self):
        for table in (self.stockTable, self.volumesTable):
            table._columnTitles = ("Stock 1", "Stock 2")
            table.resetData()
            table.populateDefault()

    def saveData(self):
        try:
            stockConcs = self.stockTable.data
            volumes = self.volumesTable.data
        except Exception as e:
            mb.showerror(title="Could not save data", message=e, parent=self)
            return

        self.titration.unknownTotalConcsLinked = \
            self.unknownTotalConcsLinkedVar.get()

        self.titration.stockConcs = stockConcs * prefixes[
            self.stockTable.unit.get().strip("M")
        ]

        self.titration.volumes = volumes * prefixes[
            self.volumesTable.unit.get().strip("L")
        ]
        self.titration.volumesUnit = self.volumesTable.unit.get()
        self.titration.rowFilter = np.in1d(
            self.titration.additionTitles, self.volumesTable.rowTitles
        )

        self.destroy()


class GetTotalConcsFromVolumes(moduleFrame.Strategy):
    def __init__(self, titration):
        self.titration = titration
        titration.getConcVarsCount = self.getConcVarsCount

    def __call__(self, totalConcVars):
        titration = self.titration
        stockConcs = np.copy(titration.stockConcs)
        if titration.unknownTotalConcsLinked:
            # For each row (= species), all blank cells are assigned to a
            # single unknown variable.
            for rowIndex, totalConcVar in zip(
                np.where(self.rowsWithBlanks)[0], totalConcVars
            ):
                stockConcs[rowIndex,
                           np.isnan(stockConcs[rowIndex])] = totalConcVar
        else:
            stockConcs[np.isnan(stockConcs)] = totalConcVars

        moles = titration.volumes @ stockConcs.T
        totalVolumes = np.atleast_2d(np.sum(titration.volumes, 1)).T
        titration.totalConcs = moles / totalVolumes

        return titration.totalConcs

    def showPopup(self):
        popup = VolumesPopup(self.titration)
        popup.wait_window(popup)

    @property
    def rowsWithBlanks(self):
        return np.isnan(np.sum(self.titration.stockConcs, 1))

    def getConcVarsCount(self):
        if self.titration.unknownTotalConcsLinked:
            # return the number of rows (= species) with blank cells
            return np.count_nonzero(self.rowsWithBlanks)
        else:
            return np.count_nonzero(np.isnan(self.titration.stockConcs))


class GetTotalConcs(moduleFrame.Strategy):
    def __init__(self, titration):
        self.titration = titration

    def __call__(self, totalConcVars):
        # TODO: implement unknown concentrations
        return self.titration.totalConcs


class ModuleFrame(moduleFrame.ModuleFrame):
    frameLabel = "Total concentrations"
    dropdownLabelText = "Enter concentrations or volumes:"
    dropdownOptions = {
        "Volumes": GetTotalConcsFromVolumes,
        "Concentrations": GetTotalConcs
    }
    attributeName = "getTotalConcs"
    setDefault = False
