from __future__ import annotations

from rest_framework import serializers

from apps.roles.models import Role, RoleSkill, Skill


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ("id", "name", "slug", "description")


class RoleSkillNestedSerializer(serializers.ModelSerializer):
    skill = SkillSerializer(read_only=True)

    class Meta:
        model = RoleSkill
        fields = ("id", "skill", "importance")


class RoleSerializer(serializers.ModelSerializer):
    skills = RoleSkillNestedSerializer(source="role_skills", many=True, read_only=True)

    class Meta:
        model = Role
        fields = ("id", "name", "slug", "description", "skills")
