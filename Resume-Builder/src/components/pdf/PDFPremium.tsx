import {
  Document,
  Page,
  Text,
  View,
  StyleSheet,
} from "@react-pdf/renderer";
import type { ResumeData } from "@appTypes/resume";

const accent = "#4f46e5";
const accentLight = "#e0e7ff";

const styles = StyleSheet.create({
  page: {
    padding: 0,
    fontSize: 9,
    fontFamily: "Helvetica",
  },
  headerBlock: {
    backgroundColor: accent,
    padding: 28,
    marginBottom: 20,
    alignItems: "center",
  },
  headerName: {
    fontSize: 22,
    fontWeight: "bold",
    color: "#fff",
    marginBottom: 4,
    textAlign: "center",
  },
  headerRole: {
    fontSize: 11,
    color: "#c7d2fe",
    textAlign: "center",
  },
  headerContact: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
    marginTop: 10,
    fontSize: 8,
    color: "#a5b4fc",
    justifyContent: "center",
  },
  content: {
    paddingHorizontal: 28,
    paddingBottom: 28,
  },
  section: {
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 11,
    fontWeight: "bold",
    color: accent,
    marginBottom: 8,
    borderLeftWidth: 3,
    borderLeftColor: accent,
    paddingLeft: 8,
  },
  summaryText: {
    lineHeight: 1.45,
    textAlign: "justify",
  },
  timelineItem: {
    flexDirection: "row",
    marginBottom: 12,
  },
  timelineDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: accent,
    marginTop: 4,
    marginRight: 12,
  },
  timelineContent: {
    flex: 1,
  },
  timelineHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: 2,
  },
  roleCompany: {
    fontWeight: "bold",
    fontSize: 10,
  },
  dates: {
    fontSize: 8,
    color: "#666",
  },
  location: {
    fontSize: 8,
    color: "#777",
    marginBottom: 4,
  },
  bullet: {
    flexDirection: "row",
    marginLeft: 4,
    marginBottom: 2,
    lineHeight: 1.35,
  },
  bulletDot: {
    width: 4,
    marginRight: 6,
  },
  skillsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  skillCell: {
    width: "30%",
    backgroundColor: accentLight,
    padding: 8,
    borderRadius: 4,
    fontSize: 9,
  },
  eduRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: 6,
  },
  certRow: {
    flexDirection: "row",
    marginBottom: 4,
    fontSize: 9,
  },
  certName: {
    fontWeight: "bold",
    width: "40%",
  },
  certIssuerYear: {
    width: "60%",
    color: "#555",
  },
});

function contactLine(c: ResumeData["contact"]): string {
  const parts = [c.email, c.phone, c.location].filter(Boolean);
  if (c.website) parts.push(c.website);
  if (c.linkedin) parts.push("LinkedIn");
  if (c.github) parts.push("GitHub");
  return parts.join("  ·  ");
}

type Certification = { name?: string; issuer?: string; year?: string };

function getCertifications(data: ResumeData): Certification[] {
  const certs = data.extras?.certifications;
  if (Array.isArray(certs)) return certs as Certification[];
  return [];
}

export function PDFPremium({ data }: { data: ResumeData }) {
  const { contact, summary, experiences, education, skills } = data;
  const allSkills = skills.flatMap((g) => g.skills);
  const certifications = getCertifications(data);

  return (
    <Document>
      <Page size="A4" style={styles.page}>
        <View style={styles.headerBlock}>
          <Text style={styles.headerName}>{contact.fullName || "Your Name"}</Text>
          {contact.headline ? (
            <Text style={styles.headerRole}>{contact.headline}</Text>
          ) : null}
          {(contact.email || contact.phone || contact.location) && (
            <Text style={styles.headerContact}>{contactLine(contact)}</Text>
          )}
        </View>

        <View style={styles.content}>
          {summary ? (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Summary</Text>
              <Text style={styles.summaryText}>{summary}</Text>
            </View>
          ) : null}

          {allSkills.length > 0 ? (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Skills</Text>
              <View style={styles.skillsGrid}>
                {allSkills.map((s, i) => (
                  <View key={i} style={styles.skillCell}>
                    <Text>{s}</Text>
                  </View>
                ))}
              </View>
            </View>
          ) : null}

          {experiences.length > 0 ? (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Experience</Text>
              {experiences.map((exp) => (
                <View key={exp.id} style={styles.timelineItem}>
                  <View style={styles.timelineDot} />
                  <View style={styles.timelineContent}>
                    <View style={styles.timelineHeader}>
                      <Text style={styles.roleCompany}>
                        {exp.role}
                        {exp.company ? `, ${exp.company}` : ""}
                      </Text>
                      <Text style={styles.dates}>
                        {exp.startDate}
                        {exp.endDate ? ` – ${exp.endDate}` : ""}
                      </Text>
                    </View>
                    {exp.location ? (
                      <Text style={styles.location}>{exp.location}</Text>
                    ) : null}
                    {exp.highlights?.map((bullet, i) => (
                      <View key={i} style={styles.bullet}>
                        <Text style={styles.bulletDot}>•</Text>
                        <Text>{bullet}</Text>
                      </View>
                    ))}
                  </View>
                </View>
              ))}
            </View>
          ) : null}

          {education.length > 0 ? (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Education</Text>
              {education.map((edu) => (
                <View key={edu.id} style={styles.eduRow}>
                  <Text>
                    {edu.degree}
                    {edu.fieldOfStudy ? `, ${edu.fieldOfStudy}` : ""}
                    {edu.school ? ` — ${edu.school}` : ""}
                  </Text>
                  <Text style={{ fontSize: 8, color: "#666" }}>
                    {edu.startDate}
                    {edu.endDate ? ` – ${edu.endDate}` : ""}
                  </Text>
                </View>
              ))}
            </View>
          ) : null}

          {certifications.length > 0 ? (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Certifications</Text>
              {certifications.map((cert, i) => (
                <View key={i} style={styles.certRow}>
                  <Text style={styles.certName}>{cert.name || "—"}</Text>
                  <Text style={styles.certIssuerYear}>
                    {[cert.issuer, cert.year].filter(Boolean).join(" · ")}
                  </Text>
                </View>
              ))}
            </View>
          ) : null}
        </View>
      </Page>
    </Document>
  );
}
