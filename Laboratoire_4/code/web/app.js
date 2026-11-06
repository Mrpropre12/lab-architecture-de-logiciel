/* Client web de l'API REST (labo 4, bonus). Meme API que l'interface PySide6.
   Securite : les donnees recues ne sont jamais inserees comme HTML (textContent seulement) ;
   les images protegees sont telechargees avec le jeton puis affichees par URL blob. */
"use strict";

const API = "/api/v1";
const STATUTS = { OUVERT: ["Ouvert", "○"], ASSIGNE: ["Assigné", "●"], VALIDATION: ["Validation", "⧗"],
                  TERMINE: ["Terminé", "✓"], FERME: ["Fermé", "—"] };
const PRIORITES = { BASSE: ["Basse", "1"], NORMALE: ["Normale", "2"], HAUTE: ["Haute", "3"] };
const ROLES = { Rapporteur: "Rapporteur", Developpeur: "Développeur", Administrateur: "Administrateur" };
const COMPTES_DEMO = [["Alice", "alice@uqac.ca", "alice-2026", "administratrice"],
                      ["Remi", "remi@uqac.ca", "remi-2026", "rapporteur"],
                      ["Rita", "rita@uqac.ca", "rita-2026", "rapporteuse"],
                      ["Diane", "diane@uqac.ca", "diane-2026", "développeuse"],
                      ["Damien", "damien@uqac.ca", "damien-2026", "développeur"]];

const etat = { jeton: null, profil: null, archives: false, courant: null, blobs: [] };
const $ = (selecteur) => document.querySelector(selecteur);

/* ------------------------------------------------ outils */
function el(balise, attributs = {}, ...enfants) {
  const n = document.createElement(balise);
  for (const [cle, valeur] of Object.entries(attributs)) {
    if (cle === "texte") n.textContent = valeur;
    else if (cle.startsWith("on")) n.addEventListener(cle.slice(2), valeur);
    else if (valeur !== false && valeur != null) n.setAttribute(cle, valeur === true ? "" : valeur);
  }
  for (const e of enfants) if (e != null) n.append(e);
  return n;
}
const date = (iso) => (iso ? new Date(iso).toLocaleString("fr-CA", { dateStyle: "medium", timeStyle: "short" }) : "");
function pastille(type, valeur) {
  const [libelle, icone] = (type === "s" ? STATUTS : PRIORITES)[valeur];
  return el("span", { class: `pastille ${type}-${valeur}`, "data-icone": icone, texte: libelle });
}
function stocker(cle, valeur) {  // confort seulement : la page fonctionne sans
  try { valeur == null ? sessionStorage.removeItem(cle) : sessionStorage.setItem(cle, valeur); } catch (_) { /* rien */ }
}
function lire(cle) { try { return sessionStorage.getItem(cle); } catch (_) { return null; } }

/* ------------------------------------------------ appel de l'API : toujours {ok, donnees, motif, details, cause} */
async function api(methode, chemin, corps, { formulaire = null, blob = false } = {}) {
  const entetes = {};
  if (etat.jeton) entetes.Authorization = `Bearer ${etat.jeton}`;
  let body;
  if (formulaire) body = formulaire;
  else if (corps !== undefined) { entetes["Content-Type"] = "application/json"; body = JSON.stringify(corps); }
  let r;
  try {
    r = await fetch(API + chemin, { method: methode, headers: entetes, body });
  } catch (_) {
    return { ok: false, motif: "serveur injoignable", details: [], cause: "INJOIGNABLE" };
  }
  if (r.ok) {
    if (blob) return { ok: true, donnees: await r.blob() };
    return { ok: true, donnees: r.status === 204 ? null : await r.json() };
  }
  let erreur;
  try { erreur = await r.json(); } catch (_) { erreur = { motif: `réponse inattendue du serveur (HTTP ${r.status})`, cause: "INJOIGNABLE" }; }
  const resultat = { ok: false, motif: erreur.motif, details: erreur.details || [], cause: erreur.cause };
  if (r.status === 401 && etat.jeton) { oublier(); afficherConnexion(); }
  return resultat;
}

/* Bandeau : meme role que BandeauResultat du labo 3 (message d'etat annonce sans deplacer le focus). */
function annoncer(r, succes) {
  const b = $("#bandeau");
  b.replaceChildren();
  b.className = "bandeau " + (r.ok ? "ok" : "refus");
  b.append(el("strong", { texte: r.ok ? "OK" : "REFUSÉ" }), " : ", r.ok ? succes : r.motif);
  const details = r.details || [];
  if (details.length) b.append(el("ul", {}, ...details.map((d) => el("li", { texte: d }))));
  b.hidden = false;
  return r.ok;
}

/* ------------------------------------------------ connexion */
function oublier() { etat.jeton = null; etat.profil = null; stocker("jeton", null); }

function afficherConnexion() {
  $("#vue-app").hidden = true;
  $("#compte").hidden = true;
  $("#vue-connexion").hidden = false;
  $("#courriel").focus();
}

async function connecter(evenement) {
  evenement.preventDefault();
  const r = await api("POST", "/sessions", { courriel: $("#courriel").value, mot_de_passe: $("#mot-de-passe").value });
  if (!r.ok) { annoncer(r); return; }
  etat.jeton = r.donnees.jeton;
  stocker("jeton", etat.jeton);
  $("#mot-de-passe").value = "";
  $("#bandeau").hidden = true;
  await demarrer(r.donnees.profil);
}

async function demarrer(profil) {
  etat.profil = profil;
  const peut = (p) => profil.permissions.includes(p);
  $("#compte-nom").textContent = `${profil.nom} (${profil.roles.map((r) => ROLES[r] || r).join(", ")})`;
  $("#compte").hidden = false;
  $("#vue-connexion").hidden = true;
  $("#vue-app").hidden = false;
  $("#ouvrir-nouveau").hidden = !peut("CREATE");
  $("#filtre").querySelector('option[value="tous"]').hidden = !peut("VIEW_ALL");
  $("#filtre").value = peut("VIEW_ALL") ? "tous" : "mes_tickets";
  $("#detail").hidden = true;
  etat.courant = null;
  await chargerListe();
  $("#principal").focus();
}

/* ------------------------------------------------ liste */
async function chargerListe() {
  let r;
  if (etat.archives) r = await api("GET", "/archives");
  else {
    const p = new URLSearchParams({ filtre: $("#filtre").value });
    if ($("#filtre-statut").value) p.set("statut", $("#filtre-statut").value);
    if ($("#filtre-priorite").value) p.set("priorite", $("#filtre-priorite").value);
    r = await api("GET", "/tickets?" + p);
  }
  const corps = $("#table-tickets tbody");
  corps.replaceChildren();
  if (!r.ok) { annoncer(r); return; }
  for (const t of r.donnees) {
    corps.append(el("tr", { class: t.numero === etat.courant ? "choisi" : null },
      el("td", { texte: t.numero }),
      el("td", {}, el("button", { type: "button", class: "lien", texte: t.titre,
                                  "aria-label": `Ouvrir le ticket ${t.numero} : ${t.titre}`,
                                  onclick: () => ouvrir(t.numero) })),
      el("td", {}, pastille("s", t.statut)), el("td", {}, pastille("p", t.priorite)),
      el("td", { texte: t.auteur }), el("td", { texte: t.assigne || "aucun" }), el("td", { texte: date(t.modifie_le) })));
  }
  $("#liste-vide").hidden = r.donnees.length > 0;
}

function basculerOnglet(archives) {
  etat.archives = archives;
  $("#onglet-actifs").setAttribute("aria-pressed", String(!archives));
  $("#onglet-archives").setAttribute("aria-pressed", String(archives));
  $("#filtres").hidden = archives;
  chargerListe();
}

async function creer(evenement) {
  evenement.preventDefault();
  const r = await api("POST", "/tickets", { titre: $("#nouveau-titre").value, priorite: $("#nouveau-priorite").value,
                                           texte: $("#nouveau-texte").value });
  if (!annoncer(r, `ticket ${r.ok ? r.donnees.numero : ""} créé`)) return;
  $("#form-nouveau").reset();
  $("#form-nouveau").hidden = true;
  await chargerListe();
  await ouvrir(r.donnees.numero);
}

/* ------------------------------------------------ detail */
async function ouvrir(numero, garderFocus = false) {
  const r = await api("GET", `/tickets/${numero}`);
  if (!r.ok) { annoncer(r); return; }
  etat.courant = numero;
  etat.blobs.forEach((u) => URL.revokeObjectURL(u));
  etat.blobs = [];
  const d = r.donnees;
  const tete = d.blocs[0];
  $("#titre-detail").textContent = `Ticket ${tete.numero} : ${tete.titre}`;
  const meta = $("#meta");
  meta.replaceChildren();
  const ligne = (cle, valeur) => meta.append(el("dt", { texte: cle }), el("dd", {}, valeur));
  ligne("Statut", pastille("s", tete.statut));
  ligne("Priorité", pastille("p", tete.priorite));
  ligne("Auteur", tete.auteur);
  ligne("Assigné", tete.assigne || "aucun");
  ligne("Créé le", date(tete.cree_le));
  ligne("Modifié le", date(tete.modifie_le));
  if (tete.archive_le) ligne("Archivé le", date(tete.archive_le));

  const description = $("#description");
  description.replaceChildren();
  const commentaires = $("#commentaires");
  commentaires.replaceChildren();
  for (const b of d.blocs.slice(1)) {
    if (b.type === "texte") description.append(el("pre", { texte: b.texte }));
    else if (b.type === "image") description.append(await figureImage(b));
    else if (b.type === "video") description.append(el("p", { class: "secondaire", texte: `Vidéo ${b.nom} : non prise en charge dans cette version.` }));
    else if (b.type === "commentaire") commentaires.append(el("li", {}, el("span", { class: "auteur", texte: b.auteur }),
      el("span", { class: "secondaire", texte: ` · ${date(b.publie_le)}` }), el("br"), b.texte));
  }
  if (!description.children.length) description.append(el("p", { class: "secondaire", texte: "Aucune description." }));
  if (!commentaires.children.length) commentaires.append(el("li", { class: "secondaire", texte: "Aucun commentaire." }));
  await afficherActions(numero, new Set(d.actions), tete);
  $("#detail").hidden = false;
  document.querySelectorAll("#table-tickets tbody tr").forEach((tr) =>
    tr.classList.toggle("choisi", tr.firstChild.textContent === String(numero)));
  if (!garderFocus) $("#titre-detail").focus();
}

async function figureImage(b) {
  const alt = b.largeur ? `Image ${b.nom}, ${b.largeur} × ${b.hauteur} pixels` : `Image ${b.nom}, illisible`;
  const figure = el("figure", {}, el("figcaption", { texte: alt }));
  const r = await api("GET", b.url.slice(API.length), undefined, { blob: true });
  if (r.ok && b.largeur) {
    const url = URL.createObjectURL(r.donnees);
    etat.blobs.push(url);
    figure.prepend(el("img", { src: url, alt, width: b.largeur, height: b.hauteur }));
  }
  return figure;
}

/* ------------------------------------------------ actions : seulement celles que le modele permet maintenant */
const NOMS_ACTIONS = { EDIT: "modifier le titre", ATTACH: "compléter la description", ASSIGN: "assigner",
  SUBMIT: "soumettre", VALIDATE: "valider", REJECT: "rejeter", CLOSE: "fermer", REOPEN: "rouvrir",
  SET_PRIORITY: "changer la priorité", ARCHIVE: "archiver", COMMENT: "commenter" };

async function agir(numero, promesse, succes) {
  const r = await promesse;
  if (annoncer(r, succes)) { await ouvrir(numero, true); await chargerListe(); }
  return r.ok;
}

function formulaire(titre, champs, bouton, surEnvoi, classeBouton = "principal") {
  const id = "f-" + Math.random().toString(36).slice(2, 8);
  const f = el("form", { "aria-labelledby": id }, el("strong", { id, texte: titre }), ...champs,
               el("div", { class: "boutons" }, el("button", { type: "submit", class: classeBouton, texte: bouton })));
  f.addEventListener("submit", async (e) => { e.preventDefault(); if (await surEnvoi()) f.reset(); });
  return f;
}
function champ(libelle, controle) {
  controle.id = controle.id || "c-" + Math.random().toString(36).slice(2, 8);
  return [el("label", { for: controle.id, texte: libelle }), controle];
}

async function afficherActions(numero, permises, tete) {
  const zone = $("#actions");
  zone.replaceChildren();
  const noms = [...permises].filter((p) => NOMS_ACTIONS[p]).map((p) => NOMS_ACTIONS[p]);
  $("#possible").textContent = "Possible maintenant : " + (noms.length ? noms.join(", ") : "consulter seulement") + ".";
  const transition = (action, corps = {}) => api("POST", `/tickets/${numero}/transitions`, { action, ...corps });
  const simple = [];
  if (permises.has("SUBMIT")) simple.push(["Soumettre à la validation", () => transition("soumettre"), "soumis à la validation"]);
  if (permises.has("VALIDATE")) simple.push(["Valider", () => transition("valider"), "travail validé"]);
  if (simple.length) zone.append(el("div", { class: "rangee" }, ...simple.map(([texte, appel, succes]) =>
    el("button", { type: "button", class: "principal", texte, onclick: () => agir(numero, appel(), succes) }))));

  for (const [p, action, titre] of [["REJECT", "rejeter", "Rejeter le travail"], ["CLOSE", "fermer", "Fermer le ticket"],
                                    ["REOPEN", "rouvrir", "Rouvrir le ticket"]]) {
    if (!permises.has(p)) continue;
    const motif = el("input", { required: true, maxlength: 500 });
    zone.append(formulaire(titre, champ("Motif (obligatoire)", motif), titre.split(" ")[0],
      () => agir(numero, transition(action, { motif: motif.value }), `ticket : ${action}`), "danger"));
  }
  if (permises.has("ASSIGN")) {
    const r = await api("GET", "/comptes?assignables=true");
    const choix = el("select", {}, ...(r.ok ? r.donnees : []).map((c) =>
      el("option", { value: c.numero, texte: c.nom, selected: c.nom === tete.assigne })));
    zone.append(formulaire("Assigner", champ("Développeur", choix), "Assigner",
      () => agir(numero, transition("assigner", { assigne: Number(choix.value) }), "ticket assigné")));
  }
  if (permises.has("EDIT")) {
    const titre = el("input", { required: true, maxlength: 200, value: tete.titre });
    zone.append(formulaire("Modifier le titre", champ("Nouveau titre", titre), "Enregistrer",
      () => agir(numero, api("PATCH", `/tickets/${numero}`, { titre: titre.value }), "titre modifié")));
  }
  if (permises.has("SET_PRIORITY")) {
    const choix = el("select", {}, ...Object.entries(PRIORITES).map(([v, [libelle]]) =>
      el("option", { value: v, texte: libelle, selected: v === tete.priorite })));
    zone.append(formulaire("Changer la priorité", champ("Priorité", choix), "Changer",
      () => agir(numero, api("PATCH", `/tickets/${numero}`, { priorite: choix.value }), "priorité changée")));
  }
  if (permises.has("ATTACH")) {
    const texte = el("textarea", { rows: 3, required: true });
    zone.append(formulaire("Ajouter un texte à la description", champ("Texte", texte), "Ajouter",
      () => agir(numero, api("POST", `/tickets/${numero}/textes`, { texte: texte.value }), "texte ajouté")));
    const fichier = el("input", { type: "file", accept: ".png,.jpg,.jpeg,.gif", required: true });
    zone.append(formulaire("Joindre une image", champ("Image .png, .jpg ou .gif (10 Mo au plus)", fichier), "Joindre",
      () => {
        const donnees = new FormData();
        donnees.append("fichier", fichier.files[0]);
        return agir(numero, api("POST", `/tickets/${numero}/images`, undefined, { formulaire: donnees }), "image jointe");
      }));
  }
  if (permises.has("COMMENT")) {
    const texte = el("textarea", { rows: 2, required: true });
    zone.append(formulaire("Commenter", champ("Commentaire", texte), "Publier",
      () => agir(numero, api("POST", `/tickets/${numero}/commentaires`, { texte: texte.value }), "commentaire publié")));
  }
  if (permises.has("ARCHIVE")) {
    const confirmer = el("button", { type: "button", class: "danger", hidden: true,
      texte: "Confirmer : archiver définitivement",
      onclick: () => agir(numero, api("POST", "/archives", { numero }), "ticket archivé") });
    zone.append(el("div", { class: "rangee" },
      el("button", { type: "button", texte: "Archiver…", "aria-expanded": "false",
        onclick: (e) => { confirmer.hidden = false; e.currentTarget.setAttribute("aria-expanded", "true"); confirmer.focus(); } }),
      confirmer));
  }
}

/* ------------------------------------------------ demarrage */
function preparer() {
  for (const [v, [libelle]] of Object.entries(STATUTS)) $("#filtre-statut").append(el("option", { value: v, texte: libelle }));
  for (const [v, [libelle]] of Object.entries(PRIORITES)) {
    $("#filtre-priorite").append(el("option", { value: v, texte: libelle }));
    $("#nouveau-priorite").append(el("option", { value: v, texte: libelle, selected: v === "NORMALE" }));
  }
  for (const [nom, courriel, mdp, role] of COMPTES_DEMO) {
    $("#comptes-demo").append(el("li", {}, el("button", { type: "button", class: "lien",
      texte: `${nom} (${role}) : ${courriel} / ${mdp}`,
      onclick: () => { $("#courriel").value = courriel; $("#mot-de-passe").value = mdp; $("#mot-de-passe").focus(); } })));
  }
  $("#form-connexion").addEventListener("submit", connecter);
  $("#deconnexion").addEventListener("click", () => { oublier(); $("#bandeau").hidden = true; afficherConnexion(); });
  $("#filtres").addEventListener("change", chargerListe);
  $("#onglet-actifs").addEventListener("click", () => basculerOnglet(false));
  $("#onglet-archives").addEventListener("click", () => basculerOnglet(true));
  $("#ouvrir-nouveau").addEventListener("click", () => { $("#form-nouveau").hidden = false; $("#nouveau-titre").focus(); });
  $("#annuler-nouveau").addEventListener("click", () => { $("#form-nouveau").reset(); $("#form-nouveau").hidden = true; });
  $("#form-nouveau").addEventListener("submit", creer);
}

async function reprendre() {  // un jeton encore valide dans cet onglet : pas besoin de se reconnecter
  etat.jeton = lire("jeton");
  if (etat.jeton) {
    const r = await api("GET", "/moi");
    if (r.ok) { await demarrer(r.donnees); return; }
    oublier();
  }
  afficherConnexion();
}

preparer();
reprendre();
