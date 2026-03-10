import os
import csv
from datetime import time
from django.core.management.base import BaseCommand
from core.models import Teacher, Course, Room, TimeSlot, Section, TeacherCourseMapping

class Command(BaseCommand):
    help = "Import initial data from CSV files in the Datasets folder"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing data before importing",
        )

    def handle(self, *args, **options):
        self.datasets_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))),
            "Datasets",
        )

        if options["clear"]:
            self.stdout.write(self.style.WARNING("Clearing existing data..."))
            TeacherCourseMapping.objects.all().delete()
            Teacher.objects.all().delete()
            Course.objects.all().delete()
            Room.objects.all().delete()
            TimeSlot.objects.all().delete()
            Section.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("  ✓ Data cleared"))

        self.import_teachers()
        self.import_courses()
        self.import_rooms()
        self.import_timeslots()
        self.import_sections()
        self.import_teacher_course_mappings()
        self.import_elective_allocations()
        self.print_summary()

    def import_teachers(self):
        """Import teachers from teachers1.csv and teachers2.csv"""
        self.stdout.write("\nImporting teachers...")
        count = 0
        for filename in ["teachers1.csv", "teachers2.csv"]:
            filepath = os.path.join(self.datasets_path, filename)
            
            if not os.path.exists(filepath):
                self.stdout.write(self.style.WARNING(f"  File not found: {filename}"))
                continue

            with open(filepath, "r") as file:
                content = file.read(2048)
                file.seek(0)
                dialect = csv.Sniffer().sniff(content) if ',' in content or '\t' in content else None
                reader = csv.DictReader(file, dialect=dialect) if dialect else csv.DictReader(file)
                for row in reader:
                    Teacher.objects.update_or_create(
                        teacher_id=row["teacher_id"].strip(),
                        defaults={
                            "teacher_name": row["teacher_name"].strip(),
                            "email": row["email"].strip(),
                            "department": row["department"].strip(),
                            "max_hours_per_week": int(row["max_hours_per_week"]),
                        },
                    )
                    count += 1
        self.stdout.write(self.style.SUCCESS(f"  ✓ Imported {count} teachers"))

    def import_courses(self):
        """Import courses from elective_courses_updated.csv (primary source)"""
        self.stdout.write("\nImporting courses from elective_courses_updated.csv...")
        count = 0
        
        filepath = os.path.join(self.datasets_path, "elective_courses_updated.csv")
        if not os.path.exists(filepath):
            self.stdout.write(self.style.ERROR(f"  File not found: elective_courses_updated.csv"))
            return

        with open(filepath, "r", encoding="utf-8") as file:
            content = file.read(2048)
            file.seek(0)
            dialect = csv.Sniffer().sniff(content) if ',' in content or '\t' in content else None
            reader = csv.DictReader(file, dialect=dialect) if dialect else csv.DictReader(file)
            for row in reader:
                course_id = row["course_id"].strip()
                is_adm = "ADM" in course_id.upper()
                
                e_group = row.get("elective_group", "NA").strip()
                if e_group == "NA" or not e_group:
                    e_group = None
                    
                is_sched = True
                if "is_schedulable" in row:
                    is_sched = str(row["is_schedulable"]).strip() == "1"
                
                # Force Year 4 to be schedulable based on user request "timetable is not generated for 4th year classes"
                if int(row["year"]) == 4:
                    is_sched = True
                
                # ADM courses are not electives by definition in this university
                is_elective = str(row["is_elective"]).strip() == "1"
                if is_adm:
                    is_elective = False

                lectures = int(row["lectures"])
                theory = int(row["theory"])
                practicals = int(row["practicals"])
                csv_weekly_slots = int(row["weekly_slots"])
                
                computed_weekly_slots = lectures + theory + practicals
                if csv_weekly_slots != computed_weekly_slots:
                    self.stdout.write(self.style.ERROR(f"Data inconsistency in {course_id}: weekly_slots={csv_weekly_slots} vs computed={computed_weekly_slots}. Rejecting record."))
                    continue

                Course.objects.update_or_create(
                    course_id=course_id,
                    defaults={
                        "course_name": row["course_name"].strip(),
                        "year": int(row["year"]),
                        "semester": row["semester"].strip().lower(),
                        "lectures": lectures,
                        "theory": theory, # used for tutorials
                        "practicals": practicals,
                        "credits": int(row["credits"]),
                        "is_lab": str(row["is_lab"]).strip() == "1",
                        "is_elective": is_elective,
                        "is_adm": is_adm,
                        "elective_type": row.get("elective_type", "").strip() or None,
                        "weekly_slots": computed_weekly_slots,
                        "elective_group": e_group,
                        "is_schedulable": is_sched,
                    },
                )
                count += 1
        self.stdout.write(self.style.SUCCESS(f"  ✓ Imported {count} courses"))

    def import_rooms(self):
        """Import rooms from rooms.csv"""
        self.stdout.write("\nImporting rooms...")
        filepath = os.path.join(self.datasets_path, "rooms.csv")
        if not os.path.exists(filepath):
            self.stdout.write(self.style.ERROR("  File not found: rooms.csv"))
            return
        count = 0
        with open(filepath, "r") as file:
            reader = csv.DictReader(file)
            for row in reader:
                room_type_val = row["room_type"].upper()
                if room_type_val == "LECTURE":
                    room_type_val = "CLASSROOM"
                Room.objects.update_or_create(
                    room_id=row["room_id"].strip(),
                    defaults={
                        "block": row["block"].strip(),
                        "floor": int(row["floor"]),
                        "room_type": room_type_val,
                        "capacity": int(row.get("capacity", 60)),
                    },
                )
                count += 1
        self.stdout.write(self.style.SUCCESS(f"  ✓ Imported {count} rooms"))

    def import_timeslots(self):
        """Import timeslots from timeslots.csv"""
        self.stdout.write("\nImporting timeslots...")
        filepath = os.path.join(self.datasets_path, "timeslots.csv")
        if not os.path.exists(filepath):
            self.stdout.write(self.style.ERROR("  File not found: timeslots.csv"))
            return
        count = 0
        with open(filepath, "r") as file:
            reader = csv.DictReader(file)
            for row in reader:
                start_h, start_m = map(int, row["start_time"].split(":"))
                end_h, end_m = map(int, row["end_time"].split(":"))
                TimeSlot.objects.update_or_create(
                    slot_id=row["slot_id"].strip(),
                    defaults={
                        "day": row["day"].strip(),
                        "slot_number": int(row["slot_number"]),
                        "start_time": time(start_h, start_m),
                        "end_time": time(end_h, end_m),
                    },
                )
                count += 1
        self.stdout.write(self.style.SUCCESS(f"  ✓ Imported {count} timeslots"))

    def import_sections(self):
        """Import sections from classes.csv"""
        self.stdout.write("\nImporting sections...")
        filepath = os.path.join(self.datasets_path, "classes.csv")
        if not os.path.exists(filepath):
            self.stdout.write(self.style.ERROR("  File not found: classes.csv"))
            return
        count = 0
        with open(filepath, "r") as file:
            reader = csv.DictReader(file)
            for row in reader:
                Section.objects.update_or_create(
                    class_id=row["class_id"].strip(),
                    defaults={
                        "year": int(row["year"]),
                        "section": row["section"].strip(),
                        "department": row["department"].strip(),
                    },
                )
                count += 1
        self.stdout.write(self.style.SUCCESS(f"  ✓ Imported {count} sections"))

    def import_teacher_course_mappings(self):
        """Import mappings from oddMapping.csv and evenMapping.csv"""
        self.stdout.write("\nImporting teacher-course mappings...")
        count = 0
        skipped = 0
        for filename in ["mapping1.csv", "mapping2.csv"]:
            filepath = os.path.join(self.datasets_path, filename)
            if not os.path.exists(filepath):
                self.stdout.write(self.style.WARNING(f"  File not found: {filename}"))
                continue
            with open(filepath, "r") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if not row.get("teacher_id") or not row.get("course_id"):
                        continue
                    try:
                        teacher = Teacher.objects.get(teacher_id=row["teacher_id"].strip())
                        course = Course.objects.get(course_id=row["course_id"].strip())
                        TeacherCourseMapping.objects.update_or_create(
                            teacher=teacher,
                            course=course,
                            section=None,
                            year=course.year,
                            defaults={"preference_level": 3},
                        )
                        count += 1
                    except (Teacher.DoesNotExist, Course.DoesNotExist):
                        skipped += 1
        self.stdout.write(self.style.SUCCESS(f"  ✓ Imported {count} mappings (Skipped {skipped})"))

    def import_elective_allocations(self):
        """Import elective allocations from elective_allocation.csv"""
        self.stdout.write("\nImporting elective allocations...")
        filepath = os.path.join(self.datasets_path, "elective_allocation.csv")
        if not os.path.exists(filepath):
            self.stdout.write(self.style.WARNING("  File not found: elective_allocation.csv"))
            return
            
        count = 0
        skipped = 0
        with open(filepath, "r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                if not row.get("teacher_id") or not row.get("course_id"):
                    continue
                try:
                    teacher = Teacher.objects.get(teacher_id=row["teacher_id"].strip())
                    course = Course.objects.get(course_id=row["course_id"].strip())
                    section_grp = row.get("section_group", "").strip() or None
                    
                    TeacherCourseMapping.objects.update_or_create(
                        teacher=teacher,
                        course=course,
                        section=None,
                        year=course.year,
                        defaults={
                            "preference_level": 3,
                            "section_group": section_grp
                        },
                    )
                    count += 1
                except (Teacher.DoesNotExist, Course.DoesNotExist):
                    skipped += 1
        self.stdout.write(self.style.SUCCESS(f"  ✓ Imported {count} elective allocations (Skipped {skipped})"))

    def print_summary(self):
        """Print summary of imported data"""
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS("DATA IMPORT SUMMARY"))
        self.stdout.write("=" * 50)
        self.stdout.write(f"Teachers:                {Teacher.objects.count()}")
        self.stdout.write(f"Courses:                 {Course.objects.count()}")
        self.stdout.write(f"Rooms:                   {Room.objects.count()}")
        self.stdout.write(f"Time Slots:              {TimeSlot.objects.count()}")
        self.stdout.write(f"Sections:                {Section.objects.count()}")
        self.stdout.write(f"Mappings:                {TeacherCourseMapping.objects.count()}")
        self.stdout.write("=" * 50)
