
import org.matsim.api.core.v01.Scenario;
import org.matsim.api.core.v01.population.Person;
import org.matsim.core.config.ConfigUtils;
import org.matsim.core.scenario.ScenarioUtils;
import org.matsim.core.population.io.PopulationReader;

public class PopProbe {
    public static void main(String[] args) throws Exception {
        Scenario sc = ScenarioUtils.createScenario(ConfigUtils.createConfig());
        new PopulationReader(sc).readFile(args[0]);
        long n = sc.getPopulation().getPersons().size();
        double ef = 0.0; long withEf = 0; long missing = 0;
        for (Person p : sc.getPopulation().getPersons().values()) {
            Object v = p.getAttributes().getAttribute("expansionFactor");
            if (v == null) { missing++; continue; }
            try { ef += Double.parseDouble(v.toString()); withEf++; }
            catch (Exception e) { missing++; }
        }
        System.out.println("PROBE_PERSONS=" + n);
        System.out.printf("PROBE_SUMEF=%.6f%n", ef);
        System.out.println("PROBE_WITH_EF=" + withEf);
        System.out.println("PROBE_MISSING_EF=" + missing);
    }
}
