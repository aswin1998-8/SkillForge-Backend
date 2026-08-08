"""Role and skill catalog models."""

from __future__ import annotations

from django.db import models


class Role(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Skill(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class RoleSkill(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_skills")
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="role_skills")
    importance = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        unique_together = ("role", "skill")
        ordering = ["role_id", "importance", "skill_id"]

    def __str__(self) -> str:
        return f"{self.role.slug}:{self.skill.slug}"
