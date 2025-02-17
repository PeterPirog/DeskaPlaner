import matplotlib
# Ustawienie backendu na TkAgg – pozwala uniknąć problemów z wyświetlaniem wykresów
matplotlib.use('TkAgg')

import matplotlib.pyplot as plt
from ortools.sat.python import cp_model
import os

def generuj_opcje_arkuszy(oryginalne_arkusze, dopuszczalny_podzial=True):
    """
    Generuje dostępne opcje arkuszy:
      - Dla każdego arkusza oryginalnego (z kluczem "number_of_items")
        tworzy tyle instancji, ile wynosi "number_of_items".
      - Jeśli dopuszczalny_podzial=True, dla każdej instancji tworzone są dodatkowe
        warianty: arkusz podzielony na pół (po szerokości lub wysokości) oraz wersja ćwiartkowa.
      - Ceny wariantów są obliczane jako:
            - 1/2 ceny oryginalnej dla wariantów "half_width" i "half_height"
            - 1/4 ceny oryginalnej dla wariantu "quarter"
    """
    opcje_arkuszy = []
    for arkusz in oryginalne_arkusze:
        liczba_instancji = arkusz.get("number_of_items", 1)
        for idx in range(liczba_instancji):
            # Oryginalny arkusz – tworzymy instancję
            instancja = arkusz.copy()
            instancja["id"] = f'{arkusz["id"]}_{idx+1}'
            opcje_arkuszy.append(instancja)

            if dopuszczalny_podzial:
                # Arkusz podzielony na pół (po szerokości)
                polowa_szerokosci = {
                    "width": arkusz["width"] // 2,
                    "height": arkusz["height"],
                    "price": arkusz["price"] / 2,  # 1/2 ceny oryginalnej
                    "id": f'{arkusz["id"]}_half_width_{idx+1}'
                }
                # Arkusz podzielony na pół (po wysokości)
                polowa_wysokosci = {
                    "width": arkusz["width"],
                    "height": arkusz["height"] // 2,
                    "price": arkusz["price"] / 2,  # 1/2 ceny oryginalnej
                    "id": f'{arkusz["id"]}_half_height_{idx+1}'
                }
                # Arkusz w ćwiartce (podział obu wymiarów)
                cwiartka = {
                    "width": arkusz["width"] // 2,
                    "height": arkusz["height"] // 2,
                    "price": arkusz["price"] / 4,  # 1/4 ceny oryginalnej
                    "id": f'{arkusz["id"]}_quarter_{idx+1}'
                }
                opcje_arkuszy.extend([polowa_szerokosci, polowa_wysokosci, cwiartka])

    return opcje_arkuszy


def rysuj_wykres(arkusz, elementy, przypisanie_elementu,
                 polozenie_x, polozenie_y,
                 szerokosci_elementow, wysokosci_elementow,
                 solver):
    """
    Funkcja pomocnicza do wizualizacji rozmieszczenia elementów
    na jednym, konkretnym arkuszu.
    """
    fig, ax = plt.subplots()
    ax.set_title(f"Arkusz {arkusz['id']} ({arkusz['width']}x{arkusz['height']} mm)")
    ax.set_xlim(0, arkusz["width"])
    ax.set_ylim(0, arkusz["height"])
    ax.set_xticks(range(0, arkusz["width"] + 1, 500))
    ax.set_yticks(range(0, arkusz["height"] + 1, 500))
    ax.set_aspect('equal')  # Ustawienie identycznej skali dla obu osi
    ax.grid(True)

    # Rysujemy obrys arkusza
    ax.add_patch(plt.Rectangle((0, 0), arkusz["width"], arkusz["height"],
                               edgecolor='black', facecolor='none', lw=2))

    # Rysujemy elementy przypisane do danego arkusza
    for i in range(len(elementy)):
        # Jeżeli przypisanie_elementu[i] == identyfikator arkusza, to rysujemy:
        # Uwaga: W modelu przypisanie_elementu to indeks arkusza w tablicy opcje_arkuszy,
        # a tutaj sprawdzamy solver.Value(...) i porównujemy z arkuszem['id'].
        #
        # Jednak w Twoim kodzie 'przypisanie_elementu' to int (index w liście),
        # a 'arkusz["id"]' to string. Aby sprawdzić, czy to ten sam arkusz,
        # musielibyśmy mieć jakieś odwzorowanie index -> arkusz["id"].
        #
        # Jeżeli chcesz użyć porównania:
        #   if solver.Value(przypisanie_elementu[i]) == arkusz["id"]:
        # to przypisanie_elementu[i] musiałoby przechowywać ID (string) zamiast int.
        #
        # Najczęściej w modelu: solver.Value(przypisanie_elementu[i]) daje s_idx,
        # a s_idx to index w liście opcje_arkuszy. Dlatego zazwyczaj
        # porównujemy z indexem, np. if solver.Value(przypisanie_elementu[i]) == s_idx.
        pass

    plt.show()


def main(oryginalne_arkusze,
         dopuszczalny_podzial,
         grubosc_krawedzi,
         elementy,
         guillotine_cutting=False):
    """
    Główna funkcja budująca i rozwiązująca model cięcia arkuszy.

    Parametry:
      - oryginalne_arkusze: lista słowników z danymi arkuszy (wymiary, cena, id, number_of_items)
      - dopuszczalny_podzial: bool, czy generować dodatkowe opcje arkuszy (1/2 i 1/4)
      - grubosc_krawedzi: grubość krawędzi cięcia (mm)
      - elementy: lista krotek (szerokość, wysokość) elementów do wycięcia
      - guillotine_cutting: bool, czy wymuszać „gilotynowe” cięcia (True/False)
    """

    # --- Opcjonalnie: w tym miejscu można wprowadzić dodatkowe ograniczenia
    # wymuszające "gilotynowy" sposób cięcia, zależnie od guillotine_cutting. ---
    if guillotine_cutting:
        print("[INFO] Guillotine cutting (gilotynowe cięcie) jest WŁĄCZONE.")
    else:
        print("[INFO] Guillotine cutting (gilotynowe cięcie) jest WYŁĄCZONE.")

    # Współczynnik skalujący ceny (aby traktować je jako liczby całkowite)
    wspolczynnik_skalujacy = 100

    # Generowanie wszystkich opcji arkuszy
    opcje_arkuszy = generuj_opcje_arkuszy(oryginalne_arkusze, dopuszczalny_podzial)

    # Obliczamy "price_int" (koszt całkowity w liczbach całkowitych)
    for arkusz in opcje_arkuszy:
        arkusz["price_int"] = int(round(arkusz["price"] * wspolczynnik_skalujacy))

    liczba_opcji = len(opcje_arkuszy)
    liczba_elementow = len(elementy)

    # ==========================
    # Budowa modelu CP-SAT
    # ==========================
    model = cp_model.CpModel()

    # Zmienna (dla każdego elementu): index arkusza, do którego jest przypisany
    przypisanie_elementu = [
        model.NewIntVar(0, liczba_opcji - 1, f'przypisanie_{i}')
        for i in range(liczba_elementow)
    ]

    # Zmienna (dla każdego elementu): czy element zostanie obrócony
    obrocony = [model.NewBoolVar(f'obrocony_{i}') for i in range(liczba_elementow)]

    # Maksymalne wymiary, potrzebne do ograniczenia położenia elementów
    max_szerokosc = max(arkusz["width"] for arkusz in opcje_arkuszy)
    max_wysokosc = max(arkusz["height"] for arkusz in opcje_arkuszy)

    # Zmienne: pozycja (x, y) dla każdego elementu
    polozenie_x = [
        model.NewIntVar(0, max_szerokosc, f'x_{i}')
        for i in range(liczba_elementow)
    ]
    polozenie_y = [
        model.NewIntVar(0, max_wysokosc, f'y_{i}')
        for i in range(liczba_elementow)
    ]

    # Zmienne: rzeczywiste wymiary elementu w modelu (uwzględnia obrócenie)
    szerokosci_elementow = []
    wysokosci_elementow = []

    for i, (szer, wys) in enumerate(elementy):
        szerokosc_e = model.NewIntVar(0, max_szerokosc, f'szer_{i}')
        wysokosc_e = model.NewIntVar(0, max_wysokosc, f'wys_{i}')

        # Jeżeli obrocony[i] == False -> szerokosc_e = szer, wysokosc_e = wys
        model.Add(szerokosc_e == szer).OnlyEnforceIf(obrocony[i].Not())
        model.Add(wysokosc_e == wys).OnlyEnforceIf(obrocony[i].Not())

        # Jeżeli obrocony[i] == True -> szerokosc_e = wys, wysokosc_e = szer
        model.Add(szerokosc_e == wys).OnlyEnforceIf(obrocony[i])
        model.Add(wysokosc_e == szer).OnlyEnforceIf(obrocony[i])

        szerokosci_elementow.append(szerokosc_e)
        wysokosci_elementow.append(wysokosc_e)

    # --- Ograniczenia: element musi się mieścić w arkuszu, do którego został przypisany ---
    wskazniki_przypisania = {}
    for i in range(liczba_elementow):
        for s in range(liczba_opcji):
            wskaznik = model.NewBoolVar(f'przypisany_{i}_{s}')
            wskazniki_przypisania[(i, s)] = wskaznik

            # Jeśli przypisanie_elementu[i] == s, to wskaźnik = True
            model.Add(przypisanie_elementu[i] == s).OnlyEnforceIf(wskaznik)
            model.Add(przypisanie_elementu[i] != s).OnlyEnforceIf(wskaznik.Not())

            # Jeżeli dany element przypisujemy do arkusza s, to musi się w nim zmieścić
            arkusz = opcje_arkuszy[s]
            model.Add(
                polozenie_x[i] + szerokosci_elementow[i] + grubosc_krawedzi <= arkusz["width"]
            ).OnlyEnforceIf(wskaznik)
            model.Add(
                polozenie_y[i] + wysokosci_elementow[i] + grubosc_krawedzi <= arkusz["height"]
            ).OnlyEnforceIf(wskaznik)

    # --- Ograniczenie: elementy nie mogą nachodzić na siebie w obrębie tego samego arkusza ---
    for i in range(liczba_elementow):
        for j in range(i + 1, liczba_elementow):
            # Zmienna logiczna: "ten_sam_arkusz" (True, jeśli elementy i, j przypisane do tego samego arkusza)
            ten_sam_arkusz = model.NewBoolVar(f'ten_sam_arkusz_{i}_{j}')

            model.Add(przypisanie_elementu[i] == przypisanie_elementu[j]).OnlyEnforceIf(ten_sam_arkusz)
            model.Add(przypisanie_elementu[i] != przypisanie_elementu[j]).OnlyEnforceIf(ten_sam_arkusz.Not())

            # Zmienne logiczne do rozdzielenia elementów w poziomie/pionie:
            lewo = model.NewBoolVar(f'lewo_{i}_{j}')
            prawo = model.NewBoolVar(f'prawo_{i}_{j}')
            gora = model.NewBoolVar(f'gora_{i}_{j}')
            dol = model.NewBoolVar(f'dol_{i}_{j}')

            # i jest "z lewej strony" j
            model.Add(
                polozenie_x[i] + szerokosci_elementow[i] + grubosc_krawedzi <= polozenie_x[j]
            ).OnlyEnforceIf(lewo)

            # i jest "z prawej strony" j
            model.Add(
                polozenie_x[j] + szerokosci_elementow[j] + grubosc_krawedzi <= polozenie_x[i]
            ).OnlyEnforceIf(prawo)

            # i jest "poniżej" j
            model.Add(
                polozenie_y[i] + wysokosci_elementow[i] + grubosc_krawedzi <= polozenie_y[j]
            ).OnlyEnforceIf(dol)

            # i jest "powyżej" j
            model.Add(
                polozenie_y[j] + wysokosci_elementow[j] + grubosc_krawedzi <= polozenie_y[i]
            ).OnlyEnforceIf(gora)

            # Jeśli elementy w tym samym arkuszu -> muszą być rozdzielone (jedno z powyższych True)
            model.AddBoolOr([lewo, prawo, gora, dol]).OnlyEnforceIf(ten_sam_arkusz)

    # --- Zmienne: czy dany arkusz (instancja) został w ogóle użyty ---
    arkusz_uzyty = []
    for s in range(liczba_opcji):
        a_used = model.NewBoolVar(f'arkusz_uzyty_{s}')
        arkusz_uzyty.append(a_used)

    # Powiązanie arkusza_uzyty ze wskaźnikami przypisania elementów
    for s in range(liczba_opcji):
        wskazniki = [wskazniki_przypisania[(i, s)] for i in range(liczba_elementow)]
        # Jeśli arkusz jest użyty, to ma >= 1 przypisany element
        model.Add(sum(wskazniki) <= liczba_elementow * arkusz_uzyty[s])
        model.Add(arkusz_uzyty[s] <= sum(wskazniki))

    # --- Cel: minimalizacja łącznego kosztu użytych arkuszy ---
    koszt_calosciowy = model.NewIntVar(0,
                                       sum(a["price_int"] for a in opcje_arkuszy),
                                       'koszt_calosciowy')
    model.Add(
        koszt_calosciowy == sum(opcje_arkuszy[s]["price_int"] * arkusz_uzyty[s]
                                for s in range(liczba_opcji))
    )
    model.Minimize(koszt_calosciowy)

    # ==========================
    # Rozwiązywanie modelu
    # ==========================
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print("Znaleziono rozwiązanie!\n")
        # Wyświetlenie przyporządkowań elementów
        for i in range(liczba_elementow):
            s_idx = solver.Value(przypisanie_elementu[i])
            arkusz = opcje_arkuszy[s_idx]
            obrot = solver.Value(obrocony[i])

            # Obliczamy wymiary (jeśli obrócony, zamiana szer <-> wys)
            wymiary_elem = (elementy[i][1], elementy[i][0]) if obrot else elementy[i]

            print(
                f"Element {i} {elementy[i]} "
                f"(obrót: {bool(obrot)}) -> Arkusz {arkusz['id']} "
                f"({arkusz['width']}x{arkusz['height']}), pozycja: "
                f"({solver.Value(polozenie_x[i])}, {solver.Value(polozenie_y[i])})"
            )
        # Wyświetlenie kosztu w jednostkach pieniężnych
        print(f"\nŁączny koszt: {solver.Value(koszt_calosciowy) / wspolczynnik_skalujacy:.2f}")

        # ==========================
        # Wizualizacja i zapis wykresów
        # ==========================
        katalog_wykresow = "wykresy"
        os.makedirs(katalog_wykresow, exist_ok=True)

        # Indeksy użytych arkuszy (wg solvera)
        uzyte_arkusze = {solver.Value(przypisanie_elementu[i]) for i in range(liczba_elementow)}

        # Dla każdego użytego arkusza - rysunek
        for s_idx in uzyte_arkusze:
            arkusz = opcje_arkuszy[s_idx]
            fig, ax = plt.subplots()
            ax.set_aspect('equal')   # ustawienie równych osi
            # Tytuł wykresu
            ax.set_title(f"Arkusz {arkusz['id']} "
                         f"({arkusz['width']}x{arkusz['height']} mm)")
            ax.set_xlim(0, arkusz["width"])
            ax.set_ylim(0, arkusz["height"])
            ax.set_xticks(range(0, arkusz["width"] + 1, 500))
            ax.set_yticks(range(0, arkusz["height"] + 1, 500))
            ax.grid(True)

            # Rysowanie granic arkusza
            ax.add_patch(plt.Rectangle((0, 0),
                                       arkusz["width"],
                                       arkusz["height"],
                                       edgecolor='black',
                                       facecolor='none',
                                       lw=2))

            # Informacja o wymiarach arkusza
            ax.text(10,
                    arkusz["height"] - 30,
                    f"{arkusz['width']}x{arkusz['height']} mm",
                    fontsize=12,
                    color='red',
                    backgroundcolor='white')

            # Rysowanie elementów przypisanych do danego arkusza
            for i in range(liczba_elementow):
                if solver.Value(przypisanie_elementu[i]) == s_idx:
                    rx = solver.Value(polozenie_x[i])
                    ry = solver.Value(polozenie_y[i])
                    rw = solver.Value(szerokosci_elementow[i])
                    rh = solver.Value(wysokosci_elementow[i])

                    rect = plt.Rectangle((rx, ry), rw, rh,
                                         edgecolor='blue',
                                         facecolor='cyan',
                                         alpha=0.5)
                    ax.add_patch(rect)

                    # Tekst / etykieta wewnątrz prostokąta
                    wymiary_elem = (elementy[i][1], elementy[i][0]) if solver.Value(obrocony[i]) else elementy[i]
                    etykieta = f"P{i} {wymiary_elem}"
                    ax.text(rx + 5, ry + 5, etykieta, color="black", fontsize=10)

            # Zapis wykresu do pliku
            sciezka_pliku = os.path.join(katalog_wykresow, f"arkusz_{arkusz['id']}.png")
            fig.savefig(sciezka_pliku, dpi=300, bbox_inches='tight')
            print(f'Wykres arkusza {arkusz["id"]} zapisany jako: {sciezka_pliku}')

            plt.show()

    else:
        print("Nie znaleziono rozwiązania.")


if __name__ == '__main__':
    # ------------------------
    # Dane wejściowe (przykład)
    # ------------------------
    oryginalne_arkusze = [
        {
            "width": 600,
            "height": 300,
            "price": 29.70,
            "id": "arkusz 600x300",
            "number_of_items": 5
        },
        {
            "width": 1200,
            "height": 600,
            "price": 65.01,
            "id": "arkusz 1200x600",
            "number_of_items": 5
        },
        {
            "width": 800,
            "height": 400,
            "price": 40.00,
            "id": "arkusz 800x400",
            "number_of_items": 5
        },
        {
            "width": 2500,
            "height": 1250,
            "price": 203.10,
            "id": "arkusz 2500x1250",
            "number_of_items": 5
        },
    ]

    # Czy włączyć opcję "gilotynowych" cięć (tu niezaimplementowane)
    guillotine_cutting = True

    # Czy generować warianty 1/2 i 1/4 arkusza
    dopuszczalny_podzial = True

    # Grubość krawędzi cięcia
    grubosc_krawedzi = 3

    # Elementy do wycięcia: (szerokość, wysokość)
    elementy = [
        (832, 620),  # Plecy
        (110, 655),  # Dół 2
        (379, 612),  # Góra
        (832, 379),  # Bok
        (832, 379),  # Bok
        (60, 655),   # Kant dolny
        (80, 620),   # Kant górny 2
        (150, 620),  # Kant górny 1
    ]

    main(
        oryginalne_arkusze,
        dopuszczalny_podzial,
        grubosc_krawedzi,
        elementy,
        guillotine_cutting=guillotine_cutting
    )
