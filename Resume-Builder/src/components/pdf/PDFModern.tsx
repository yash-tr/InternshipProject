import {
  Document,
  Page,
  Text,
  View,
  StyleSheet,
} from "@react-pdf/renderer";
import type { ResumeData } from "@appTypes/resume";

const teal = "#0d9488";
const tealLight = "#ccfbf1";

const styles = StyleSheet.create({
  page: {
    flexDirection: "row",
    fontSize: 9,
    fontFamily: "Helvetica",
  },
  sidebar: {
    width: "30%",
    backgroundColor: "#f0fdfa",
    padding: 20,
  },
  main: {
    width: "70%",
    padding: 24,
  },
  name: {
    fontSize: 18,
    fontWeight: "bold",
    color: teal,
    marginBottom: 4,
    textAlign: "center",
  },
  headline: {
    fontSize: 9,
    color: "#555",
    marginBottom: 16,
    textAlign: "center",
  },
  sideSection: {
    marginBottom: 14,
  },
  sideTitle: {
    fontSize: 10,
    fontWeight: "bold",
    color: teal,
    marginBottom: 6,
    borderBottomWidth: 1,
    borderBottomColor: teal,
    paddingBottom: 2,
  },
  sideText: {
    lineHeight: 1.4,
    color: "#333",
  },
  sideLink: {
    color: teal,
    marginBottom: 2,
  },
  mainSection: {
    marginBottom: 14,
  },
  mainTitle: {
    fontSize: 11,
    fontWeight: "bold",
    color: teal,
    marginBottom: 6,
    borderBottomWidth: 1,
    borderBottomColor: teal,
    paddingBottom: 2,
  },
  summaryText: {
    lineHeight: 1.45,
    textAlign: "justify",
  },
  expBlock: {
    marginBottom: 10,
  },
  expHeader: {
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
    marginLeft: 6,
    marginBottom: 2,
    lineHeight: 1.35,
  },
  bulletDot: {
    width: 4,
    marginRight: 4,
    color: teal,
  },
  skillItem: {
    marginBottom: 3,
  },
  eduItem: {
    marginBottom: 6,
  },
  eduDegree: {
    fontWeight: "bold",
    fontSize: 9,
  },
  eduSchool: {
    fontSize: 8,
    color: "#555",
  },
});

function contactLine(c: ResumeData["contact"]): string[] {
  const lines: string[] = [];
  if (c.email) lines.push(c.email);
  if (c.phone) lines.push(c.phone);
  if (c.location) lines.push(c.location);
  if (c.website) lines.push(c.website);
  if (c.linkedin) lines.push(c.linkedin);
  if (c.github) lines.push(c.github);
  return lines;
}

export function PDFModern({ data }: { data: ResumeData }) {
  const { contact, summary, experiences, education, skills } = data;
  const contactLines = contactLine(contact);
  const allSkills = skills.flatMap((g) => g.skills);

  return (
    <Document>
      <Page size="A4" style={styles.page}>
        <View style={styles.sidebar}>
          <Text style={styles.name}>{contact.fullName || "Your Name"}</Text>
          {contact.headline ? (
            <Text style={styles.headline}>{contact.headline}</Text>
          ) : null}
          {contactLines.length > 0 ? (
            <View style={styles.sideSection}>
              <Text style={styles.sideTitle}>Contact</Text>
              {contactLines.map((line, i) => (
                <Text key={i} style={styles.sideLink}>
                  {line}
                </Text>
              ))}
            </View>
          ) : null}
          {allSkills.length > 0 ? (
            <View style={styles.sideSection}>
              <Text style={styles.sideTitle}>Skills</Text>
              {allSkills.map((s, i) => (
                <Text key={i} style={styles.skillItem}>
                  {s}
                </Text>
              ))}
            </View>
          ) : null}
          {education.length > 0 ? (
            <View style={styles.sideSection}>
              <Text style={styles.sideTitle}>Education</Text>
              {education.map((edu) => (
                <View key={edu.id} style={styles.eduItem}>
                  <Text style={styles.eduDegree}>
                    {edu.degree}
                    {edu.fieldOfStudy ? `, ${edu.fieldOfStudy}` : ""}
                  </Text>
                  <Text style={styles.eduSchool}>
                    {edu.school}
                    {edu.startDate || edu.endDate
                      ? ` · ${[edu.startDate, edu.endDate].filter(Boolean).join(" – ")}`
                      : ""}
                  </Text>
                </View>
              ))}
            </View>
          ) : null}
        </View>
        <View style={styles.main}>
          {summary ? (
            <View style={styles.mainSection}>
              <Text style={styles.mainTitle}>Summary</Text>
              <Text style={styles.summaryText}>{summary}</Text>
            </View>
          ) : null}
          {experiences.length > 0 ? (
            <View style={styles.mainSection}>
              <Text style={styles.mainTitle}>Experience</Text>
              {experiences.map((exp) => (
                <View key={exp.id} style={styles.expBlock}>
                  <View style={styles.expHeader}>
                    <Text style={styles.roleCompany}>
                      {exp.role}
                      {exp.company ? ` at ${exp.company}` : ""}
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
        </View>
      </Page>
    </Document>
  );
}
