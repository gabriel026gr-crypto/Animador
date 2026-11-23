"""Roteiro do EP. 3 — "Quem cai?" (Simula Aí!).

Cada cena tem uma duração-alvo (do briefing) e uma lista de frases.
Cada frase tem o texto da LEGENDA (como aparece na tela) e o texto FALADO
(normalizado para o TTS: números por extenso, grafias que forçam a
pronúncia certa, ex.: "Ínter", "Corintians").
"""

SCENES = [
    {"id": 1, "target": 5.0, "lines": [
        ("Inter e Grêmio no Z4 ao mesmo tempo.",
         "Ínter e Grêmio no zê quatro, ao mesmo tempo."),
        ("E a matemática não tá ajudando.",
         "E a matemática não tá ajudando."),
    ]},
    {"id": 2, "target": 10.0, "lines": [
        ("Na 35ª rodada, o Inter perdeu pro Vasco por 2 a 1,",
         "Na trigésima quinta rodada, o Ínter perdeu pro Vasco por dois a um,"),
        ("e o Grêmio só empatou com o Bahia em casa.",
         "e o Grêmio só empatou com o Bahia, em casa."),
        ("Enquanto isso, o Corinthians meteu 4 a 0 no Botafogo",
         "Enquanto isso, o Corintians meteu quatro a zero no Botafogo,"),
        ("e o Vitória venceu o Bragantino.",
         "e o Vitória venceu o Bragantino."),
    ]},
    {"id": 3, "target": 9.0, "lines": [
        ("Lá embaixo ficou assim:",
         "Lá embaixo ficou assim:"),
        ("Coritiba com 42, Vitória e Mirassol com 41,",
         "Coritiba com quarenta e dois, Vitória e Mirassol com quarenta e um,"),
        ("Corinthians com 40...",
         "Corintians com quarenta..."),
        ("e a dupla Gre-Nal com 38.",
         "e a dupla Grenal, com trinta e oito."),
    ]},
    {"id": 4, "target": 14.0, "lines": [
        ("Eu simulei 200 mil vezes os jogos que faltam.",
         "Eu simulei duzentas mil vezes os jogos que faltam."),
        ("O Grêmio cai em 71% das vezes.",
         "O Grêmio cai em setenta e um por cento das vezes."),
        ("O Inter, em 60.",
         "O Ínter, em sessenta."),
        ("Mirassol 22, Vitória 18,",
         "Mirassol, vinte e dois. Vitória, dezoito."),
        ("Corinthians 16 e Coritiba 10.",
         "Corintians, dezesseis. E Coritiba, dez."),
    ]},
    {"id": 5, "target": 8.0, "lines": [
        ("Os dois gaúchos caem juntos em 40% das simulações.",
         "Os dois gaúchos caem juntos em quarenta por cento das simulações."),
        ("E em 9 de cada 10, pelo menos um deles cai.",
         "E em nove de cada dez, pelo menos um deles cai."),
    ]},
    {"id": 6, "target": 9.0, "lines": [
        ("A conta da salvação é 44 pontos.",
         "A conta da salvação é quarenta e quatro pontos."),
        ("Pra chegar lá, Grêmio e Inter precisam de",
         "Pra chegar lá, Grêmio e Ínter precisam de"),
        ("duas vitórias e um empate nos três jogos que faltam.",
         "duas vitórias e um empate, nos três jogos que faltam."),
    ]},
    {"id": 7, "target": 13.0, "lines": [
        ("E na próxima rodada tem decisão: Inter e Vitória.",
         "E na próxima rodada tem decisão: Ínter e Vitória."),
        ("Se o Inter vencer, a chance de cair despenca pra 38%.",
         "Se o Ínter vencer, a chance de cair despenca pra trinta e oito por cento."),
        ("Se empatar, sobe pra 79%.",
         "Se empatar, sobe pra setenta e nove."),
        ("Se perder, vai a 90%.",
         "Se perder, vai a noventa."),
        ("E o Grêmio visita o Santos: se ganhar, cai pra 39%.",
         "E o Grêmio visita o Santos: se ganhar, cai pra trinta e nove."),
    ]},
    {"id": 8, "target": 10.0, "lines": [
        ("E aí, quem se salva: Grêmio, Inter, ou nenhum dos dois?",
         "E aí, quem se salva? Grêmio, Ínter, ou nenhum dos dois?"),
        ("Comenta aí e segue o Simula Aí!",
         "Comenta aí, e segue o Simula Aí!"),
        ("pra acompanhar até a última rodada.",
         "pra acompanhar até a última rodada."),
    ]},
]
