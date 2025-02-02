import matplotlib
# Ustawienie backendu na TkAgg – pozwala uniknąć problemów z wyświetlaniem wykresów
matplotlib.use('TkAgg')

import matplotlib.pyplot as plt
from ortools.sat.python import cp_model
import os

def generuj_opcje_listew(oryginalne_listew):
    """
    Generuje dostępne opcje listew.
    Dla każdej listwy oryginalnej (ze zdefiniowanym kluczem "number_of_items")
    tworzy tyle instancji, ile wynosi ta wartość.
    """
    opcje_listew = []
    for listwa in oryginalne_listew:
        liczba_instancji = listwa.get("number_of_items", 1)
        for idx in range(liczba_instancji):
            instancja = listwa.copy()
            instancja["id"] = f'{listwa["id"]}_{idx+1}'
            opcje_listew.append(instancja)
    return opcje_listew

def main(oryginalne_listew, dopuszczalny_podzial, grubosc_krawedzi, elementy):
    """
    Główna funkcja budująca i rozwiązująca model jednowymiarowego cięcia listew.

    Parametry:
      - oryginalne_listew: lista słowników z danymi listew (długość, cena, id, number_of_items)
      - dopuszczalny_podzial: bool, czy generować dodatkowe warianty listew (tutaj nieużywany)
      - grubosc_krawedzi: grubość cięcia (mm)
      - elementy: lista długości elementów do wycięcia (w mm)
    """
    wspolczynnik_skalujacy = 100
    opcje_listew = generuj_opcje_listew(oryginalne_listew)
    for listwa in opcje_listew:
        listwa["price_int"] = int(round(listwa["price"] * wspolczynnik_skalujacy))

    model = cp_model.CpModel()

    przypisanie_elementu = [
        model.NewIntVar(0, len(opcje_listew) - 1, f'przypisanie_{i}')
        for i in range(len(elementy))
    ]

    pozycja = [
        model.NewIntVar(0, max(listwa["length"] for listwa in opcje_listew), f'pozycja_{i}')
        for i in range(len(elementy))
    ]

    dlugosci_elementow = []
    for i, d in enumerate(elementy):
        dl = model.NewIntVar(0, max(elementy), f'dlugosc_{i}')
        model.Add(dl == d)
        dlugosci_elementow.append(dl)

    przypisane = {}
    for i in range(len(elementy)):
        for s in range(len(opcje_listew)):
            var = model.NewBoolVar(f'przypisany_{i}_{s}')
            przypisane[(i, s)] = var
            model.Add(przypisanie_elementu[i] == s).OnlyEnforceIf(var)
            model.Add(przypisanie_elementu[i] != s).OnlyEnforceIf(var.Not())
            listwa = opcje_listew[s]
            model.Add(pozycja[i] + dlugosci_elementow[i] + grubosc_krawedzi <= listwa["length"]).OnlyEnforceIf(var)

    for s in range(len(opcje_listew)):
        suma_dlugosci = model.NewIntVar(0, 100000, f'suma_dlugosci_{s}')
        model.Add(suma_dlugosci == sum(elementy[i] * przypisane[(i, s)] for i in range(len(elementy))))
        liczba_elem_na_listwie = sum(przypisane[(i, s)] for i in range(len(elementy)))
        model.Add(suma_dlugosci + (liczba_elem_na_listwie - 1) * grubosc_krawedzi <= opcje_listew[s]["length"])

    listwa_uzyta = []
    for s in range(len(opcje_listew)):
        uzyta = model.NewBoolVar(f'listwa_uzyta_{s}')
        listwa_uzyta.append(uzyta)

    for s in range(len(opcje_listew)):
        wskazniki = [przypisane[(i, s)] for i in range(len(elementy))]
        model.Add(sum(wskazniki) <= len(elementy) * listwa_uzyta[s])
        model.Add(listwa_uzyta[s] <= sum(wskazniki))

    koszt_calosciowy = model.NewIntVar(0, sum(listwa["price_int"] for listwa in opcje_listew), 'koszt_calosciowy')
    model.Add(koszt_calosciowy == sum(opcje_listew[s]["price_int"] * listwa_uzyta[s] for s in range(len(opcje_listew))))
    model.Minimize(koszt_calosciowy)

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        uzyte_listwy = {solver.Value(przypisanie_elementu[i]) for i in range(len(elementy))}
        liczba_uzytych_listew = len(uzyte_listwy)

        katalog_wykresow = "wykresy"
        os.makedirs(katalog_wykresow, exist_ok=True)

        fig, axes = plt.subplots(nrows=liczba_uzytych_listew, figsize=(10, 2 * liczba_uzytych_listew), sharex=True)
        if liczba_uzytych_listew == 1:
            axes = [axes]  # Jeśli tylko jeden subplot, zamień na listę

        for ax, s_idx in zip(axes, uzyte_listwy):
            lista = opcje_listew[s_idx]
            ax.hlines(0, 0, lista["length"], colors='black', linewidth=4)
            ax.set_xlim(0, lista["length"] + 50)
            ax.set_ylim(-0.6, 1.5)
            ax.set_xlabel("Długość (mm)")
            ax.set_yticks([])
            ax.grid(True, axis='x')

            ax.text(lista["length"] + 10, 0, f"{lista['length']} mm", fontsize=12,
                    color='red', backgroundcolor='white', va='center', ha='left')

            for i in range(len(elementy)):
                if solver.Value(przypisanie_elementu[i]) == s_idx:
                    pos = solver.Value(pozycja[i])
                    dl = solver.Value(dlugosci_elementow[i])
                    rect = plt.Rectangle((pos, -0.3), dl, 0.6, edgecolor='blue',
                                         facecolor='cyan', alpha=0.5)
                    ax.add_patch(rect)
                    etykieta = f"P{i} ({elementy[i]} mm)"
                    ax.text(pos + dl / 2, 0.7, etykieta, color="black",
                            fontsize=10, ha='center', va='bottom', rotation=90)
                    ax.vlines([pos, pos + dl], -0.3, 0.3, colors='red', linestyles='dotted')

        plt.tight_layout()
        sciezka = os.path.join(katalog_wykresow, "wszystkie_listwy.png")
        fig.savefig(sciezka, dpi=300, bbox_inches='tight')
        print(f'Wykres wszystkich listew zapisany jako: {sciezka}')
        plt.show()
    else:
        print("Nie znaleziono rozwiązania.")

if __name__ == '__main__':
    oryginalne_listew = [
        {"length": 600, "price": 29.70, "id": "listwa 600mm", "number_of_items": 5},
        {"length": 1200, "price": 65.01, "id": "listwa 1200mm", "number_of_items": 5},
        {"length": 800, "price": 40.00, "id": "listwa 800mm", "number_of_items": 5},
        {"length": 2500, "price": 203.10, "id": "listwa 2500mm", "number_of_items": 5},
    ]

    dopuszczalny_podzial = False
    grubosc_krawedzi = 0
    elementy = [832, 110, 383, 832, 832, 60, 80, 150]

    main(oryginalne_listew, dopuszczalny_podzial, grubosc_krawedzi, elementy)
