import matplotlib
# Ustawienie backendu na TkAgg – powinno rozwiązać problem z 'tostring_rgb'
matplotlib.use('TkAgg')

import matplotlib.pyplot as plt
from ortools.sat.python import cp_model
import os

def generate_sheet_options(original_sheets, allow_splitting=True):
    """
    Generuje dostępne opcje arkuszy: oryginalne oraz, jeśli allow_splitting=True,
    arkusze podzielone na połowę (szerokości lub wysokości) oraz na ćwiartkę.
    Ceny arkuszy dzielonych stanowią odpowiednio 1/2 oraz 1/4 ceny oryginalnej.
    """
    sheet_options = []
    for sheet in original_sheets:
        # Oryginalny arkusz
        sheet_options.append(sheet)
        if allow_splitting:
            # Arkusz podzielony na pół (po szerokości)
            half_width = {
                "width": sheet["width"] // 2,
                "height": sheet["height"],
                "price": sheet["price"] // 2,  # 1/2 ceny oryginalnej
                "id": f'{sheet["id"]}_half_width'
            }
            # Arkusz podzielony na pół (po wysokości)
            half_height = {
                "width": sheet["width"],
                "height": sheet["height"] // 2,
                "price": sheet["price"] // 2,  # 1/2 ceny oryginalnej
                "id": f'{sheet["id"]}_half_height'
            }
            # Arkusz o 1/4 rozmiaru (podział obu wymiarów)
            quarter = {
                "width": sheet["width"] // 2,
                "height": sheet["height"] // 2,
                "price": sheet["price"] // 4,  # 1/4 ceny oryginalnej
                "id": f'{sheet["id"]}_quarter'
            }
            sheet_options.extend([half_width, half_height, quarter])
    return sheet_options

def main():
    # ==========================
    # Dane wejściowe i ustawienia konfiguracyjne
    # ==========================

    # Oryginalne arkusze – przykładowe wymiary (w mm) i ceny
    original_sheets = [
        {"width": 2500, "height": 1250, "price": 120, "id": "sheet0"},
        {"width": 2800, "height": 2070, "price": 180, "id": "sheet1"},
    ]

    # Ustawienia konfiguracyjne
    allow_splitting = True  # Czy dodawać arkusze podzielone (1/2 i 1/4)
    cut_thickness = 10      # Grubość krawędzi cięcia (mm)

    # Elementy do wycięcia (w mm): lista krotek (szerokość, wysokość)
    pieces = [(800, 600), (1200, 600), (1000, 500), (700, 700)]

    # Generujemy opcje arkuszy na podstawie oryginalnych arkuszy i ustawienia allow_splitting
    sheet_options = generate_sheet_options(original_sheets, allow_splitting)
    num_sheet_options = len(sheet_options)
    num_pieces = len(pieces)

    # ==========================
    # Budowa modelu CP-SAT
    # ==========================
    model = cp_model.CpModel()

    # Zmienne decyzyjne:
    # Dla każdego elementu wybieramy arkusz (indeks w sheet_options)
    piece_sheet = [
        model.NewIntVar(0, num_sheet_options - 1, f'piece_sheet_{i}')
        for i in range(num_pieces)
    ]

    # Zmienna binarna określająca, czy element jest obrócony
    # (False: oryginalne wymiary, True: zamienione)
    rotated = [model.NewBoolVar(f'rotated_{i}') for i in range(num_pieces)]

    # Maksymalne wymiary spośród dostępnych arkuszy – używane przy definiowaniu zakresu współrzędnych
    max_width = max(sheet["width"] for sheet in sheet_options)
    max_height = max(sheet["height"] for sheet in sheet_options)

    # Współrzędne lewego dolnego rogu elementu
    x = [model.NewIntVar(0, max_width, f'x_{i}') for i in range(num_pieces)]
    y = [model.NewIntVar(0, max_height, f'y_{i}') for i in range(num_pieces)]

    # Wymiary elementu – zależne od rotacji
    piece_width = []
    piece_height = []
    for i, (w, h) in enumerate(pieces):
        pw = model.NewIntVar(0, max_width, f'piece_width_{i}')
        ph = model.NewIntVar(0, max_height, f'piece_height_{i}')
        # Jeśli element nie jest obracany: szerokość = w, wysokość = h
        model.Add(pw == w).OnlyEnforceIf(rotated[i].Not())
        model.Add(ph == h).OnlyEnforceIf(rotated[i].Not())
        # Jeśli element jest obracany: szerokość = h, wysokość = w
        model.Add(pw == h).OnlyEnforceIf(rotated[i])
        model.Add(ph == w).OnlyEnforceIf(rotated[i])
        piece_width.append(pw)
        piece_height.append(ph)

    # --- Ograniczenia: element musi mieścić się w arkuszu, do którego jest przypisany ---
    assigned_indicator = {}
    for i in range(num_pieces):
        for s in range(num_sheet_options):
            # Zmienna pomocnicza – True, gdy element i został przypisany do arkusza s
            assigned_indicator[(i, s)] = model.NewBoolVar(f'assigned_{i}_{s}')
            model.Add(piece_sheet[i] == s).OnlyEnforceIf(assigned_indicator[(i, s)])
            model.Add(piece_sheet[i] != s).OnlyEnforceIf(assigned_indicator[(i, s)].Not())
            # Element (z uwzględnieniem krawędzi cięcia) musi mieścić się w arkuszu
            sheet = sheet_options[s]
            model.Add(x[i] + piece_width[i] + cut_thickness <= sheet["width"]).OnlyEnforceIf(assigned_indicator[(i, s)])
            model.Add(y[i] + piece_height[i] + cut_thickness <= sheet["height"]).OnlyEnforceIf(assigned_indicator[(i, s)])

    # --- Ograniczenie: brak nachodzenia elementów na tym samym arkuszu ---
    for i in range(num_pieces):
        for j in range(i + 1, num_pieces):
            same_sheet = model.NewBoolVar(f'same_sheet_{i}_{j}')
            model.Add(piece_sheet[i] == piece_sheet[j]).OnlyEnforceIf(same_sheet)
            model.Add(piece_sheet[i] != piece_sheet[j]).OnlyEnforceIf(same_sheet.Not())
            left = model.NewBoolVar(f'left_{i}_{j}')
            right = model.NewBoolVar(f'right_{i}_{j}')
            above = model.NewBoolVar(f'above_{i}_{j}')
            below = model.NewBoolVar(f'below_{i}_{j}')
            model.Add(x[i] + piece_width[i] + cut_thickness <= x[j]).OnlyEnforceIf(left)
            model.Add(x[j] + piece_width[j] + cut_thickness <= x[i]).OnlyEnforceIf(right)
            model.Add(y[i] + piece_height[i] + cut_thickness <= y[j]).OnlyEnforceIf(below)
            model.Add(y[j] + piece_height[j] + cut_thickness <= y[i]).OnlyEnforceIf(above)
            model.AddBoolOr([left, right, above, below]).OnlyEnforceIf(same_sheet)

    # --- Zmienne informujące, czy arkusz został użyty ---
    sheet_used = []
    for s in range(num_sheet_options):
        used = model.NewBoolVar(f'sheet_used_{s}')
        sheet_used.append(used)

    # --- Powiązanie zmiennej sheet_used z przypisaniem elementów ---
    for s in range(num_sheet_options):
        indicators = [assigned_indicator[(i, s)] for i in range(num_pieces)]
        model.Add(sum(indicators) <= num_pieces * sheet_used[s])
        model.Add(sheet_used[s] <= sum(indicators))

    # --- Cel optymalizacyjny: minimalizacja łącznego kosztu użytych arkuszy ---
    total_cost = model.NewIntVar(0, sum(sheet["price"] for sheet in sheet_options), 'total_cost')
    model.Add(total_cost == sum(sheet_options[s]["price"] * sheet_used[s] for s in range(num_sheet_options)))
    model.Minimize(total_cost)

    # ==========================
    # Rozwiązywanie modelu
    # ==========================
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print("Znaleziono rozwiązanie!")
        for i in range(num_pieces):
            s_idx = solver.Value(piece_sheet[i])
            sheet = sheet_options[s_idx]
            rot = solver.Value(rotated[i])
            # Ustalamy wymiary wyświetlane w etykiecie – jeśli obrót, zamieniamy wymiary
            if rot:
                dims = (pieces[i][1], pieces[i][0])
            else:
                dims = pieces[i]
            print(f"Element {i} o wymiarach {pieces[i]} (obrót: {bool(rot)}) "
                  f"umieszczony na arkuszu {sheet['id']} "
                  f"({sheet['width']}x{sheet['height']} mm) w pozycji ({solver.Value(x[i])}, {solver.Value(y[i])})")
        print("Łączny koszt:", solver.Value(total_cost))

        # ==========================
        # Wizualizacja i zapis wykresów
        # ==========================
        output_dir = "wykresy"
        os.makedirs(output_dir, exist_ok=True)

        used_sheet_indices = {solver.Value(piece_sheet[i]) for i in range(num_pieces)}
        for s_idx in used_sheet_indices:
            sheet = sheet_options[s_idx]
            fig, ax = plt.subplots()
            ax.set_title(f'Arkusz {sheet["id"]} ({sheet["width"]}x{sheet["height"]} mm)')
            ax.set_xlim(0, sheet["width"])
            ax.set_ylim(0, sheet["height"])
            ax.set_xticks(range(0, sheet["width"] + 1, 500))
            ax.set_yticks(range(0, sheet["height"] + 1, 500))
            ax.grid(True)

            # Rysowanie granic arkusza
            ax.add_patch(plt.Rectangle((0, 0), sheet["width"], sheet["height"],
                                       edgecolor='black', facecolor='none', lw=2))
            # Dodanie tekstu z rozmiarami arkusza
            ax.text(10, sheet["height"] - 30, f'{sheet["width"]}x{sheet["height"]} mm',
                    fontsize=12, color='red', backgroundcolor='white')

            # Rysowanie elementów wraz z etykietą zawierającą wymiary
            for i in range(num_pieces):
                if solver.Value(piece_sheet[i]) == s_idx:
                    rx = solver.Value(x[i])
                    ry = solver.Value(y[i])
                    rw = solver.Value(piece_width[i])
                    rh = solver.Value(piece_height[i])
                    rect = plt.Rectangle(
                        (rx, ry),
                        rw,
                        rh,
                        edgecolor='blue', facecolor='cyan', alpha=0.5
                    )
                    ax.add_patch(rect)

                    # Ustalanie etykiety: jeśli obrót, zamieniamy wymiary
                    if solver.Value(rotated[i]):
                        dims = (pieces[i][1], pieces[i][0])
                    else:
                        dims = pieces[i]
                    label = f"P{i} {dims}"

                    ax.text(rx + 5, ry + 5, label, color="black", fontsize=10)

            # Zapis wykresu do pliku PNG
            filename = os.path.join(output_dir, f"arkusz_{sheet['id']}.png")
            fig.savefig(filename, dpi=300, bbox_inches='tight')
            print(f'Wykres arkusza {sheet["id"]} zapisany jako: {filename}')
            plt.show()
    else:
        print("Nie znaleziono rozwiązania.")

if __name__ == '__main__':
    # Oryginalne arkusze – przykładowe wymiary (w mm) i ceny
    original_sheets = [
        {"width": 2500, "height": 1250, "price": 120, "id": "sheet0"},
        {"width": 2800, "height": 2070, "price": 180, "id": "sheet1"},
    ]

    # Ustawienia konfiguracyjne
    allow_splitting = True  # Czy dodawać arkusze podzielone (1/2 i 1/4)
    cut_thickness = 10      # Grubość krawędzi cięcia (mm)

    # Elementy do wycięcia (w mm): lista krotek (szerokość, wysokość)
    pieces = [(800, 600), (1200, 600), (1000, 500), (700, 700)]

    main()
