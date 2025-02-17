import matplotlib
# Ustawienie backendu na TkAgg – zapewnia poprawne wyświetlanie wykresów
matplotlib.use('TkAgg')

import matplotlib.pyplot as plt
from ortools.sat.python import cp_model
import os

def main(sciany, dostepne_listwy, minimalny_kawalek):
    """
    Rozwiązuje problem cięcia ścian przy użyciu dostępnych listew.

    Parametry:
      - sciany: lista długości ścian do pokrycia (w mm)
      - dostepne_listwy: lista słowników opisujących dostępne listwy.
            Każdy słownik musi zawierać:
                "length" – długość listwy (mm)
                "price"  – cena listwy
                "id"     – unikalny identyfikator typu listwy
      - minimalny_kawalek: najkrótszy kawałek, który można użyć (w mm)

    Dla każdej ściany model decyduje:
      - t_j: typ listwy (indeks z dostepne_listwy)
      - n_j: liczba użytych listew tego typu (całkowita, ≥ 1)
      - r_j: długość wykorzystana z ostatniej listwy (minimalny_kawalek ≤ r_j ≤ L[t_j])

    Ograniczenie: (n_j - 1) * L[t_j] + r_j = długość ściany_j.
    Koszt ściany: n_j * cena[t_j].
    Celem jest minimalizacja łącznego kosztu.
    """
    model = cp_model.CpModel()

    num_scian = len(sciany)
    num_typow = len(dostepne_listwy)

    # Tablice długości i cen dostępnych listew
    board_lengths = [d["length"] for d in dostepne_listwy]
    board_prices = [d["price"] for d in dostepne_listwy]
    max_board_length = max(board_lengths)

    # Skalowanie cen – aby ceny były traktowane jako liczby całkowite
    scale_factor = 100
    scaled_prices = [int(round(p * scale_factor)) for p in board_prices]

    # Dla każdej ściany definiujemy zmienne:
    type_vars = []  # wybór typu listwy (indeks)
    n_vars = []     # liczba użytych listew
    delta_vars = [] # pomocnicza: delta = n - 1
    r_vars = []     # długość wykorzystana z ostatniej listwy
    z_vars = []     # pomocnicza: z = delta * L[t]
    cost_vars = []  # koszt dla ściany

    for j in range(num_scian):
        # Wybór typu listwy: wartość od 0 do num_typow-1
        t = model.NewIntVar(0, num_typow - 1, f'type_{j}')
        type_vars.append(t)
        # Maksymalna liczba listew użytych do ściany j:
        max_n = sciany[j] // minimalny_kawalek + 1
        n = model.NewIntVar(1, max_n, f'n_{j}')
        n_vars.append(n)
        # Delta: n = delta + 1
        delta = model.NewIntVar(0, max_n - 1, f'delta_{j}')
        delta_vars.append(delta)
        model.Add(n == delta + 1)

        # r: długość wykorzystana z ostatniej listwy, zakres: [minimalny_kawalek, max_board_length]
        r = model.NewIntVar(minimalny_kawalek, max_board_length, f'r_{j}')
        r_vars.append(r)

        # Pobieramy stałą długość listwy dla wybranego typu – używamy AddElement
        board_length = model.NewIntVar(0, max_board_length, f'board_length_{j}')
        model.AddElement(t, board_lengths, board_length)

        # Pobieramy skalowaną cenę listwy dla wybranego typu
        board_price = model.NewIntVar(0, max(scaled_prices), f'board_price_{j}')
        model.AddElement(t, scaled_prices, board_price)

        # Ograniczenie: r <= board_length
        model.Add(r <= board_length)

        # Zmienna pomocnicza: z = delta * board_length
        z = model.NewIntVar(0, (max_n - 1) * max_board_length, f'z_{j}')
        z_vars.append(z)
        model.AddMultiplicationEquality(z, [delta, board_length])

        # Równanie: z + r = długość ściany
        model.Add(z + r == sciany[j])

        # Koszt ściany: n * board_price
        cost_j = model.NewIntVar(0, max_n * max(scaled_prices), f'cost_{j}')
        model.AddMultiplicationEquality(cost_j, [n, board_price])
        cost_vars.append(cost_j)

    # Ustalmy górną granicę dla łącznego kosztu – obliczymy sumę maksymalnych kosztów dla każdej ściany
    upper_bound_total = sum((sciany[j] // minimalny_kawalek + 1) * max(scaled_prices) for j in range(num_scian))

    total_cost = model.NewIntVar(0, upper_bound_total, 'total_cost')
    model.Add(total_cost == sum(cost_vars))
    model.Minimize(total_cost)

    # Rozwiązywanie modelu
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print("Znaleziono rozwiązanie!")
        total = solver.Value(total_cost) / scale_factor
        print("Łączny koszt:", total)
        print("-" * 40)
        # Dla każdej ściany wypisujemy szczegółowy wynik
        for j in range(num_scian):
            t_val = solver.Value(type_vars[j])
            n_val = solver.Value(n_vars[j])
            r_val = solver.Value(r_vars[j])
            wall = sciany[j]
            board_len = board_lengths[t_val]
            board_prc = scaled_prices[t_val] / scale_factor
            print(f"Ściana o długości {wall} mm:")
            print(f"  Wybrany typ listwy: {dostepne_listwy[t_val]['id']} (długość: {board_len} mm, cena: {board_prc} jednostek)")
            print(f"  Liczba użytych listew: {n_val}")
            print(f"  Wykorzystana długość z ostatniej listwy: {r_val} mm")
            pelna = (n_val - 1) * board_len
            print(f"  Długość z pełnych listew: {pelna} mm")
            print("  Szczegółowy podział na instancje:")
            # Dla k = 1 do n-1 – pełne listwy
            for k in range(1, n_val):
                print(f"    Listwa {dostepne_listwy[t_val]['id']}_nr_{k}: użyj całości (0-{board_len} mm)")
            # Ostatnia instancja – użyty fragment
            print(f"    Listwa {dostepne_listwy[t_val]['id']}_nr_{n_val}: użyj fragmentu (0-{r_val} mm)")
            print("-" * 40)

        # Wizualizacja – dla każdej ściany tworzymy osobny wykres 1D
        katalog_wykresow = "wykresy_scian"
        os.makedirs(katalog_wykresow, exist_ok=True)
        for j in range(num_scian):
            wall = sciany[j]
            fig, ax = plt.subplots(figsize=(10, 2))
            ax.hlines(0, 0, wall, colors='black', linewidth=4)
            ax.set_xlim(0, wall + 100)
            ax.set_ylim(-0.5, 0.5)
            ax.set_xlabel("Długość ściany (mm)")
            ax.set_yticks([])
            ax.grid(True, axis='x')
            ax.text(10, 0.3, f"Ściana: {wall} mm", fontsize=12,
                    color='red', backgroundcolor='white', va='center', ha='left')

            n_val = solver.Value(n_vars[j])
            pos = 0
            # Rysujemy pełne listwy
            for k in range(n_val - 1):
                rect = plt.Rectangle((pos, -0.3), board_len, 0.6, edgecolor='blue',
                                     facecolor='cyan', alpha=0.5)
                ax.add_patch(rect)
                ax.text(pos + board_len/2, 0, f"Listwa {k+1}", color="black",
                        fontsize=10, ha='center', va='center', rotation=90)
                pos += board_len
            # Rysujemy ostatni fragment
            r_val = solver.Value(r_vars[j])
            if n_val >= 1:
                rect = plt.Rectangle((pos, -0.3), r_val, 0.6, edgecolor='blue',
                                     facecolor='cyan', alpha=0.5)
                ax.add_patch(rect)
                ax.text(pos + r_val/2, 0, f"Listwa {n_val}\n(użyto {r_val} mm)", color="black",
                        fontsize=10, ha='center', va='center', rotation=90)
            sciezka = os.path.join(katalog_wykresow, f"sciana_{j+1}.png")
            fig.savefig(sciezka, dpi=300, bbox_inches='tight')
            print(f'Wykres ściany {j+1} zapisany jako: {sciezka}')
            plt.show()
    else:
        print("Nie znaleziono rozwiązania.")

if __name__ == '__main__':
    # Definicja dostępnych listew – każda ma długość (mm), cenę i unikalny identyfikator
    dostepne_listwy = [
        {"length": 2000, "price": 50, "id": "listwa_2000"},
        {"length": 2500, "price": 60, "id": "listwa_2500"},
        {"length": 3000, "price": 70, "id": "listwa_3000"}
    ]
    # Przykładowe ściany (długości w mm)
    sciany = [5500, 4200, 6300]
    # Minimalny kawałek, który można wykorzystać (w mm)
    minimalny_kawalek = 200

    main(sciany, dostepne_listwy, minimalny_kawalek)
