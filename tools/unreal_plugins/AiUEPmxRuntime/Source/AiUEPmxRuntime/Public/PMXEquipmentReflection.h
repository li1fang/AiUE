#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "Engine/SkeletalMesh.h"
#include "PMXEquipmentReflection.generated.h"

class UPMXEquipmentLoadoutAsset;
class UPMXEquipmentPairAsset;

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
