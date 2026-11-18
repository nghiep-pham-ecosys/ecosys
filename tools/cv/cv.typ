// ATS-safe CV template (spec §5.1): one column, real text, standard headings, no tables or images.
// Data comes from `tools/cv/cv build`, which writes a JSON file and passes its path as --input data=<path>.
// The template holds no personal data, so it lives in the public ecosys repo.
#let d = json(sys.inputs.at("data"))

#set document(title: d.name + " — CV", author: d.name)
#set page(paper: "a4", margin: (x: 1.7cm, y: 1.5cm))
#set text(font: ("Liberation Sans", "DejaVu Sans"), size: 9.8pt, lang: "en")
#set par(justify: false, leading: 0.55em, spacing: 0.7em)
#set list(indent: 0.6em, body-indent: 0.45em, spacing: 0.5em)
#show link: set text(fill: rgb("#1a4f8b"))

#let accent = rgb("#1a4f8b")
#let muted = rgb("#4a4a4a")

#show heading.where(level: 2): it => {
  v(0.55em)
  block(below: 0.45em, {
    text(size: 11pt, weight: "bold", fill: accent, upper(it.body))
    v(-0.55em)
    line(length: 100%, stroke: 0.5pt + accent)
  })
}

#align(left)[
  #text(size: 19pt, weight: "bold")[#d.name] \
  #v(-0.2em)
  #text(size: 11pt, fill: accent, weight: "semibold")[#d.headline] \
  #text(fill: muted)[#d.contact.join(" · ")] \
  #d.links.map(l => link(l.url)[#l.label: #l.url.replace("https://", "")]).join(" · ")
]

#if d.summary.len() > 0 [
  == Profile
  #for p in d.summary [#p #parbreak()]
]

#if d.skills.len() > 0 [
  == Core skills
  #for s in d.skills [
    *#s.area:* #s.items \
  ]
]

#if d.work.len() > 0 [
  == Experience
  #for w in d.work [
    #block(breakable: true, above: 0.8em)[
      *#w.role · #w.org* #h(1fr) #box(text(fill: muted)[#w.dates]) \
      #if w.place != "" [#text(fill: muted, style: "italic")[#w.place]]
      #for hl in w.highlights [- #hl]
    ]
  ]
]

#if d.projects.len() > 0 [
  == Selected projects
  #for p in d.projects [
    - *#p.name:* #p.text#if p.url != "" [ (#link(p.url)[#p.url.replace("https://", "")])]
  ]
]

#if d.research.len() > 0 [
  == Research
  #for r in d.research [- #r]
]

#if d.education.len() > 0 [
  == Education
  #for e in d.education [- #e]
]

#if d.certs.len() > 0 [
  == Certifications
  #for c in d.certs [- #c]
]

#if d.languages.len() > 0 [
  == Languages
  #d.languages.join(" · ")
]
