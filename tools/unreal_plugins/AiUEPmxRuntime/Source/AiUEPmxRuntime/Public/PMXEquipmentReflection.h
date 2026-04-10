#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "Engine/SkeletalMesh.h"
#include "PMXEquipmentReflection.generated.h"

class UPMXEquipmentLoadoutAsset;
class UPMXEquipmentPairAsset;

USTRUCT(BlueprintType)
struct FPMXAnimationPoseProbeResult
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    FName BoneName = NAME_None;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    bool Found = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    bool Changed = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    float LocationDelta = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    float RotationAngleDeltaDegrees = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    float ScaleDelta = 0.0f;
};

USTRUCT(BlueprintType)
struct FPMXAnimationPoseEvaluationResult
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    bool Success = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    bool PoseChanged = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    float SampleTimeSeconds = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    int32 BoneCount = 0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    int32 ChangedBoneCount = 0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    float MaxLocationDelta = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    float MaxRotationAngleDeltaDegrees = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    float MaxScaleDelta = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    TArray<FString> AppliedMethods;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    TArray<FString> Warnings;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    TArray<FString> Errors;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    TArray<FPMXAnimationPoseProbeResult> ProbeResults;
};

USTRUCT(BlueprintType)
struct FPMXEquipmentPairEntry
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    FString SampleId;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    FString PairId;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    FString CharacterPackageId;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    FString WeaponPackageId;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    TObjectPtr<USkeletalMesh> CharacterMesh = nullptr;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    TObjectPtr<USkeletalMesh> WeaponMesh = nullptr;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    FName EquipSlot = TEXT("weapon");

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    FName AttachSocketName = TEXT("WeaponSocket");

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    bool bConsumerReady = false;
};

UCLASS(BlueprintType, Blueprintable)
class AIUEPMXRUNTIME_API UPMXEquipmentPairAsset : public UDataAsset
{
    GENERATED_BODY()

public:
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    FPMXEquipmentPairEntry Pair;
};

USTRUCT(BlueprintType)
struct FPMXEquipmentLoadoutEntry
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    FString SampleId;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    FString CharacterPackageId;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    FString DefaultWeaponPackageId;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    TObjectPtr<USkeletalMesh> CharacterMesh = nullptr;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    TObjectPtr<USkeletalMesh> WeaponMesh = nullptr;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    FName EquipSlot = TEXT("weapon");

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    FName AttachSocketName = TEXT("WeaponSocket");

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    TObjectPtr<UPMXEquipmentPairAsset> DefaultPairAsset = nullptr;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    TArray<TObjectPtr<UPMXEquipmentPairAsset>> AvailablePairAssets;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    TArray<FString> AvailableWeaponPackageIds;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    bool bConsumerReady = false;
};

UCLASS(BlueprintType, Blueprintable)
class AIUEPMXRUNTIME_API UPMXEquipmentLoadoutAsset : public UDataAsset
{
    GENERATED_BODY()

public:
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    FPMXEquipmentLoadoutEntry Loadout;
};

UCLASS(BlueprintType, Blueprintable)
class AIUEPMXRUNTIME_API UPMXEquipmentRegistryAsset : public UDataAsset
{
    GENERATED_BODY()

public:
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    FString SuiteName;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    FString SuiteSlug;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    TArray<TObjectPtr<UPMXEquipmentPairAsset>> PairAssets;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline")
    TArray<TObjectPtr<UPMXEquipmentLoadoutAsset>> CharacterLoadouts;
};
