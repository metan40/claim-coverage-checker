# Auteur : Thierry MBARGA
"""Génère le jeu d'entraînement de descriptions de sinistres (fictives).

Chaque description combine une formule d'ouverture, un événement, un lieu,
un moment et un complément, tirés au hasard (graine fixe : le fichier est
reproductible). L'étiquette est la famille de garantie qui couvre
l'événement, selon la logique des contrats habitation :

- vol : vol, cambriolage, tentative, vandalisme ;
- incendie : feu, fumée, explosion, foudre, brûlures et dommages ménagers ;
- degats_des_eaux : fuite, infiltration, débordement, gel des conduites ;
- bris_de_glace : vitre, baie vitrée, miroir, plaque vitrocéramique ;
- evenements_naturels : tempête, grêle, neige, inondation, catastrophe ;
- responsabilite_civile : dommage causé à un tiers.

Le jeu de test (``sinistres_test.csv``) est écrit à la main, dans d'autres
tournures, et n'est jamais généré : il mesure la capacité du modèle à
généraliser au-delà des gabarits.

Usage : ``python data/sinistres/generer_sinistres.py``
"""
import csv
import random
from pathlib import Path

SEED = 2026
PER_FAMILY = 130
OUT = Path(__file__).with_name("sinistres_entrainement.csv")

OPENERS = ["", "Bonjour, ", "Je déclare un sinistre : ", "Je vous écris car ", "Madame, Monsieur, ",
           "Petit problème : ", "Je souhaite savoir si je suis couvert : ", "Urgent : ",
           "Pour information, ", "Mon assurance habitation fonctionne-t-elle ? "]
TIMES = ["", " hier soir", " ce matin", " pendant nos vacances", " le week-end dernier",
         " cette nuit", " pendant mon absence", " il y a trois jours", " lundi", " en pleine journée"]
EXTRAS = ["", ".", ". Que dois-je faire ?", ". Est-ce pris en charge ?", ". J'ai pris des photos.",
          ". Le préjudice est important.", ". Je n'ai pas encore fait de devis.",
          ". Mon propriétaire est prévenu.", ". Merci de me rappeler."]

EVENTS = {
    "vol": [
        "on m'a volé mon vélo", "des cambrioleurs sont entrés chez moi", "la porte d'entrée a été forcée",
        "mon vélo électrique a disparu", "on a dérobé mes bijoux", "des voleurs ont fracturé la fenêtre",
        "ma trottinette a été volée", "on a volé la tondeuse dans l'abri de jardin",
        "des individus ont tagué la façade", "ma cave a été cambriolée", "on a tenté de forcer la serrure",
        "mon ordinateur portable a été volé", "la boîte aux lettres a été vandalisée",
        "le salon de jardin a été dérobé", "mes clés ont été volées puis l'appartement visité",
        "quelqu'un est entré par effraction", "on a volé les vélos des enfants",
        "des vandales ont crevé la porte du garage", "le coffre a été emporté par les voleurs",
        "des objets de valeur ont disparu après une effraction", "la serrure du local a été cassée et mon vélo volé",
        "on a volé ma télévision", "le garage a été visité par des voleurs",
        "mes outils ont été volés dans la dépendance", "un cambriolage a eu lieu",
    ],
    "incendie": [
        "un incendie s'est déclaré dans la cuisine", "le four a pris feu",
        "le feu a pris dans la cheminée", "la friteuse a pris feu", "un court-circuit a provoqué un départ de feu",
        "la fumée a noirci les murs du salon", "une bouteille de gaz a explosé",
        "la foudre est tombée sur la maison", "le fer à repasser a brûlé la moquette",
        "une cigarette a brûlé le canapé", "le barbecue a mis le feu à la haie",
        "une bougie a brûlé la nappe", "le radiateur a roussi les rideaux",
        "la chaudière a explosé", "les flammes ont détruit le garage", "une lampe halogène a brûlé le parquet",
        "la table en plastique a fondu à cause de la chaleur", "des braises ont brûlé le tapis",
        "le grille-pain a pris feu", "un feu de poubelle s'est propagé à la terrasse",
        "le sèche-linge a pris feu", "la chaleur du poêle a déformé le meuble",
        "des étincelles ont brûlé le mobilier de jardin", "un incendie chez le voisin a atteint ma maison",
        "la multiprise a fondu et a brûlé le bureau",
    ],
    "degats_des_eaux": [
        "une canalisation a fui", "le lave-linge a débordé", "de l'eau s'infiltre par le toit",
        "le voisin du dessus a eu une fuite", "le chauffe-eau a lâché", "un tuyau a gelé et éclaté",
        "la baignoire a débordé", "le plafond est taché par une infiltration",
        "le joint de la douche fuit", "le lave-vaisselle a inondé la cuisine",
        "une fuite sous l'évier a abîmé le meuble", "le radiateur fuit sur le parquet",
        "l'eau est remontée par les canalisations", "la toiture laisse passer l'eau",
        "le ballon d'eau chaude a percé", "une conduite enterrée s'est rompue",
        "l'aquarium a éclaté et l'eau a coulé partout", "le tuyau de la machine s'est détaché",
        "des moisissures apparaissent après une fuite", "la gouttière bouchée a fait couler l'eau dans le mur",
        "le WC a débordé", "l'eau du voisin coule dans ma salle de bain", "le parquet a gonflé à cause d'une fuite",
        "la chasse d'eau fuit depuis des jours", "le plafond s'est effondré sous le poids de l'eau",
    ],
    "bris_de_glace": [
        "la vitre de la fenêtre est cassée", "la baie vitrée s'est fissurée", "le miroir de la salle de bain est brisé",
        "la plaque vitrocéramique est fêlée", "un ballon a cassé la fenêtre", "la porte vitrée a éclaté",
        "le vitrage de la véranda est fendu", "la vitre de l'insert est cassée",
        "le double vitrage est fissuré", "la paroi de douche en verre a explosé",
        "la table en verre s'est brisée", "le velux est cassé", "la vitre de la porte d'entrée est fendue",
        "un caillou a fêlé la baie vitrée", "le verre de la crédence est fissuré",
        "le miroir de l'armoire est tombé et s'est cassé", "la fenêtre de la chambre est brisée",
        "le panneau vitré du garde-corps est cassé", "la vitre du four est fendue",
        "la vitrine du salon est brisée",
    ],
    "evenements_naturels": [
        "la tempête a arraché des tuiles", "la grêle a abîmé la toiture", "la rivière a inondé le rez-de-chaussée",
        "le poids de la neige a fait céder l'auvent", "un arbre est tombé sur le toit à cause du vent",
        "une coulée de boue a envahi le jardin", "des rafales ont renversé la clôture",
        "l'orage a provoqué une inondation de la cave", "le terrain a glissé sous la terrasse",
        "la grêle a percé la véranda", "la tempête a emporté l'abri de jardin",
        "un tremblement de terre a fissuré les murs", "les pluies torrentielles ont inondé la maison",
        "le vent a arraché l'antenne", "la crue a submergé le garage", "la sécheresse a fissuré la façade",
        "une mini-tornade a endommagé la toiture", "la neige a écrasé la serre",
        "la cave est inondée après le débordement du ruisseau", "une branche arrachée par la tempête a percé le toit",
    ],
    "responsabilite_civile": [
        "mon fils a blessé un camarade", "mon chien a mordu le facteur", "j'ai abîmé le téléphone d'un ami",
        "un pot de fleurs est tombé de mon balcon sur une voiture", "mon enfant a rayé la voiture du voisin",
        "mon chat a griffé l'enfant des voisins", "j'ai fait tomber un invité dans mon escalier",
        "ma fille a cassé les lunettes d'une amie", "mon chien a renversé un cycliste",
        "j'ai endommagé le matériel prêté par un collègue", "un invité s'est blessé chez moi",
        "mon fils a cassé la console d'un copain", "ma tondeuse a projeté un caillou sur la voiture d'un passant",
        "mon chien a détruit le jardin du voisin", "j'ai bousculé quelqu'un à vélo",
        "l'arbre de mon jardin est tombé chez le voisin", "mon enfant a mis le feu au jardin du voisin en jouant",
        "le voisin me réclame des dommages pour sa clôture abîmée par mes enfants",
        "un passant a glissé devant ma maison", "j'ai abîmé la voiture d'un tiers en déménageant",
    ],
}

PLACES = {
    "vol": ["", " dans le local à vélos de l'immeuble", " dans ma cave", " dans le garage",
            " dans l'appartement", " dans le jardin", " dans le hall de l'immeuble", " dans la maison"],
    "incendie": ["", " dans la cuisine", " sur la terrasse", " dans le salon", " dans le jardin",
                 " au sous-sol", " dans la chambre", " dans l'appartement"],
    "degats_des_eaux": ["", " dans la salle de bain", " dans la cuisine", " au sous-sol", " dans la chambre",
                        " dans l'appartement", " dans le séjour"],
    "bris_de_glace": ["", " dans le salon", " dans la cuisine", " dans la chambre", " à l'étage", " à la maison"],
    "evenements_naturels": ["", " à la maison", " chez nous", " dans notre commune", " dans le quartier"],
    "responsabilite_civile": ["", " à l'école", " dans la rue", " chez des amis", " au parc",
                              " pendant une fête"],
}


def generate(per_family: int = PER_FAMILY, seed: int = SEED) -> list[tuple[str, str]]:
    rng = random.Random(seed)
    rows: list[tuple[str, str]] = []
    for family, events in EVENTS.items():
        seen: set[str] = set()
        attempts = 0
        while len(seen) < per_family and attempts < per_family * 50:
            attempts += 1
            text = (rng.choice(OPENERS) + rng.choice(events) + rng.choice(PLACES[family])
                    + rng.choice(TIMES) + rng.choice(EXTRAS)).strip()
            text = text[0].upper() + text[1:]
            if text not in seen:
                seen.add(text)
                rows.append((text, family))
    rng.shuffle(rows)
    return rows


if __name__ == "__main__":
    rows = generate()
    with OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "description", "famille"])
        for number, (text, family) in enumerate(rows, start=1):
            writer.writerow([f"E{number:04d}", text, family])
    print(f"{len(rows)} descriptions écrites dans {OUT}")
