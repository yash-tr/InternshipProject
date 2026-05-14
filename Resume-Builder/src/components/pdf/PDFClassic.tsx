import {
  Document,
  Page,
  Text,
  View,
  StyleSheet,
} from "@react-pdf/renderer";
import type { ResumeData } from "@appTypes/resume";

const styles = StyleSheet.create({
  page: {
    padding: 40,
    fontSize: 10,
    fontFamily: "Helvetica",
  },
  header: {
    marginBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: "#000",
    paddingBottom: 8,
    alignItems: "center",
  },
  name: {
    fontSize: 24,
    fontWeight: "bold",
    marginBottom: 4,
    textAlign: "center",
  },
  contactRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    fontSize: 9,
    color: "#333",
    justifyContent: "center",
  },
  section: {
    marginTop: 14,
  },
  sectionTitle: {
    fontSize: 11,
    fontWeight: "bold",
    marginBottom: 6,
    borderBottomWidth: 0.5,
    borderBottomColor: "#000",
    paddingBottom: 2,
  },
  summaryText: {
    lineHeight: 1.4,
    textAlign: "justify",
  },
  experienceBlock: {
    marginBottom: 10,
  },
  experienceHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: 2,
  },
  roleCompany: {
    fontWeight: "bold",
    fontSize: 10,
  },
  dates: {
    fontSize: 9,
    color: "#444",
  },
  location: {
    fontSize: 9,
    color: "#555",
    marginBottom: 4,
  },
  bullet: {
    flexDirection: "row",
    marginLeft: 8,
    marginBottom: 2,
    lineHeight: 1.35,
  },
  bulletDot: {
    width: 4,
    marginRight: 6,
  },
  educationRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: 4,
  },
  skillsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
  },
  skillChip: {
    backgroundColor: "#f0f0f0",
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 2,
    fontSize: 9,
  },
});

function contactLine(c: ResumeData["contact"]): string {
  const parts = [c.email, c.phone, c.location].filter(Boolean);
  if (c.website) parts.push(c.website);
  if (c.linkedin) parts.push(c.linkedin);
  if (c.github) parts.push(c.github);
  return parts.join(" · ");
}

export function PDFClassic({ data }: { data: ResumeData }) {
  const { contact, summary, experiences, education, skills } = data;
  const allSkills = skills.flatMap((g) => g.skills);

  return (
    <Document>
      <Page size="A4" style={styles.page}>
        <View style={styles.header}>
          <Text style={styles.name}>{contact.fullName || "Your Name"}</Text>
          {(contact.headline || contactLine(contact)) && (
            <Text style={styles.contactRow}>
              {[contact.headline, contactLine(contact)].filter(Boolean).join(" · ")}
            </Text>
          )}
        </View>

        {summary ? (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Summary</Text>
            <Text style={styles.summaryText}>{summary}</Text>
          </View>
        ) : null}

        {experiences.length > 0 ? (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Experience</Text>
            {experiences.map((exp) => (
              <View key={exp.id} style={styles.experienceBlock}>
                <View style={styles.experienceHeader}>
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
            ))}
          </View>
        ) : null}

        {education.length > 0 ? (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Education</Text>
            {education.map((edu) => (
              <View key={edu.id} style={styles.educationRow}>
                <Text>
                  {edu.degree}
                  {edu.fieldOfStudy ? `, ${edu.fieldOfStudy}` : ""}
                  {edu.school ? ` — ${edu.school}` : ""}
                </Text>
                <Text style={styles.dates}>
                  {edu.startDate}
                  {edu.endDate ? ` – ${edu.endDate}` : ""}
                </Text>
              </View>
            ))}
          </View>
        ) : null}

        {allSkills.length > 0 ? (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Skills</Text>
            <View style={styles.skillsRow}>
              {allSkills.map((s, i) => (
                <Text key={i} style={styles.skillChip}>
                  {s}
                </Text>
              ))}
            </View>
          </View>
        ) : null}
      </Page>
    </Document>
  );
}
