library(tidyverse)
options(pillar.sigfig = 4) # decimal places in output displays
library(scales)

exits <- read.csv("exiter_report.csv")
earnings <- read.csv("earnings_records.csv")

dim(exits)
dim(earnings)

exits |>
  filter(ssn == 999999999) |>
  group_by(month) |>
  summarize(n())

# add reporting_quarter
# add measure quarters - out 2 and 4 quarters to help earnings data join
# join to earnings data for 2 and 4 quarters after exit
# remove placeholder SSNs
# sort by ssn & month
exits <- exits |>
  mutate(reporting_quarter = case_when(
    (month %% 100) %in% c(10, 11, 12) ~ ((month %/% 10) + 10),
    (month %% 100) %in% c(1, 2, 3) ~ ((month %/% 10) + 2),
    (month %% 100) %in% c(4, 5, 6) ~ ((month %/% 10) + 3),
    (month %% 100) %in% c(7, 8, 9) ~ ((month %/% 10) + 4),
    TRUE ~ NA
  ),
  q2 = case_when(reporting_quarter %% 10 < 3 ~ reporting_quarter + 2,
                 TRUE ~ reporting_quarter + 8),
  q4 = reporting_quarter + 10) |>
  left_join(earnings, by = join_by(q2 == qtr, ssn == ssn)) |>
  rename(q2_earnings = earnings) |>
  left_join(earnings, by = join_by(q4 == qtr, ssn == ssn)) |>
  rename(q4_earnings = earnings) |>
  filter(ssn != 999999999) |>
  arrange(ssn, month)

# check if months are consecutive, handling year change properly
is_consecutive <- function(a, b) {
  year_a <- floor(a / 100)
  month_a <- a %% 100
  year_b <- floor(b / 100)
  month_b <- b %% 100

  if (year_a == year_b) {
    return(month_b == month_a + 1)
  } else if (year_b == year_a + 1) {
    return(month_a == 12 && month_b == 1)
  }
  return(FALSE)
}

# create sequence groups
exits$sequence_group <- 0
for (i in 2:nrow(exits)) {
  if (is_consecutive(exits$month[i - 1], exits$month[i]) &&
        exits$ssn[i - 1] == exits$ssn[i]) {
    exits$sequence_group[i] <- exits$sequence_group[i - 1]
  } else {
    exits$sequence_group[i] <- exits$sequence_group[i - 1] + 1
  }
}

# keep the last observation in each sequence per SSN
exits_filtered <- exits |>
  group_by(ssn, sequence_group) |>
  slice_max(order_by = month, n = 1) |>
  ungroup() |>
  select(-sequence_group)

exits_filtered |>
  group_by(reporting_quarter) |>
  summarize(n())

## quarterly measures - deduplicated within quarter

quarterly <- exits_filtered |>
  arrange(ssn, desc(month)) |>
  group_by(reporting_quarter) |>
  distinct(ssn, .keep_all = TRUE) |>
  summarize(total = n(),
            count_q2_earnings = sum(q2_earnings > 0, na.rm = TRUE),
            rate_q2_earnings = ncar::Round(count_q2_earnings / total, 4),
            median_q2_earnings = median(q2_earnings[q2_earnings > 0],
                                        na.rm = TRUE),
            count_q4_earnings = sum(q2_earnings > 0 & q4_earnings > 0,
                                    na.rm = TRUE),
            rate_q4_earnings = ncar::Round(count_q4_earnings /
                                             count_q2_earnings, 4))

quarterly

## annual measures - deduplicated within year

annual <- exits_filtered |>
  arrange(desc(month)) |>
  distinct(ssn, .keep_all = TRUE) |>
  summarize(total = n(),
            count_q2_earnings = sum(q2_earnings > 0, na.rm = TRUE),
            rate_q2_earnings = ncar::Round(count_q2_earnings / total, 4),
            median_q2_earnings = median(q2_earnings[q2_earnings > 0],
                                        na.rm = TRUE),
            count_q4_earnings = sum(q2_earnings > 0 & q4_earnings > 0,
                                    na.rm = TRUE),
            rate_q4_earnings = ncar::Round(count_q4_earnings /
                                             count_q2_earnings, 4))

annual

## summary charts

# measures and chart labels
measures <- list(
  "rate_q2_earnings" = "Employment Rate—2nd Quarter After Exit",
  "median_q2_earnings" = "Median Earnings—2nd Quarter After Exit",
  "rate_q4_earnings" = "Employment Retention Rate—4th Quarter After Exit"
)

# format y-axis labels
format_labels <- function(value, measure) {
  if (grepl("rate", measure)) {
    return(percent(value, accuracy = 0.01))  # Convert proportion to percentage
  } else if (grepl("median", measure)) {
    return(dollar(value, accuracy = 0.01))  # Format as currency
  } else {
    return(format(value, big.mark = ","))
  }
}

# loop through each measure and create bar chart
for (measure in names(measures)) {

  # prep data
  quarterly_data <- quarterly %>%
    select(reporting_quarter, all_of(measure)) %>%
    rename(value = all_of(measure)) %>%
    mutate(reporting_quarter = as.character(reporting_quarter))

  annual_value <- annual %>% pull(all_of(measure))

  chart_data <- bind_rows(
    quarterly_data,
    tibble(reporting_quarter = "Annual", value = annual_value)
  )

  # create bar chart
  p <- ggplot(chart_data,
              aes(x = reporting_quarter, y = value, fill = reporting_quarter)) +
    geom_bar(stat = "identity", show.legend = FALSE) +
    geom_text(aes(label = format_labels(value, measure)),
              vjust = -0.5, size = 4) +
    scale_fill_manual(values = c(rep("#63bab0", nrow(quarterly_data)),
                                 "#407972")) +
    labs(title = measures[[measure]], x = NULL, y = "Value") +
    theme_minimal(base_size = 14) +
    theme(panel.grid.major.x = element_blank(),
          panel.grid.minor.x = element_blank(),
          panel.grid.major.y = element_line(linetype = "dashed",
                                            color = "gray"),
          axis.text.x = element_text(angle = 0, hjust = 0.5))

  # adjust y-axis scale based on measure type
  if (grepl("rate", measure)) {
    p <- p + scale_y_continuous(labels = percent_format(accuracy = 1),
                                limits = c(0, 1))
  } else if (grepl("median", measure)) {
    p <- p + scale_y_continuous(labels = dollar_format(accuracy = 1))
  }

  # show plot
  print(p)
}
